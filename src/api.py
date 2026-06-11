"""API REST do sistema RAG, usando FastAPI.

Endpoints:
    POST /query     -> responde uma pergunta com base nos runbooks
    GET  /health    -> status do serviço e do índice
    GET  /runbooks  -> lista os runbooks indexados com metadados

Suba com: uvicorn src.api:app --reload  (ou `make api`)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from . import config
    from .rag import RAGEngine
    from .retriever import Retriever
except ImportError:  # pragma: no cover
    import config
    from rag import RAGEngine
    from retriever import Retriever

app = FastAPI(
    title="RAG Runbooks API",
    description="Responde perguntas técnicas sobre runbooks de infraestrutura AWS.",
    version="1.0.0",
)

# Diretório do frontend estático (web/static/), servido pela própria API.
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


# ----- Modelos de entrada/saída (schema da API) -----

class QueryRequest(BaseModel):
    """Corpo da requisição de /query."""
    question: str = Field(..., min_length=1, description="Pergunta em linguagem natural.")
    top_k: int = Field(config.DEFAULT_TOP_K, ge=1, le=10, description="Nº de chunks a recuperar.")


class SourceItem(BaseModel):
    file: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    tokens: int
    cost_usd: float


# ----- Inicialização preguiçosa do engine (carrega índice/modelo uma vez) -----

@lru_cache(maxsize=1)
def get_engine() -> RAGEngine:
    """Cria e cacheia o RAGEngine; reusa entre requisições."""
    return RAGEngine()


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    """Retriever isolado para os endpoints de metadados (/health, /runbooks)."""
    return Retriever()


# ----- Endpoints -----

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """Recebe uma pergunta, executa o fluxo RAG e devolve resposta + fontes."""
    try:
        resultado = get_engine().retrieve_and_generate(req.question, top_k=req.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QueryResponse(
        answer=resultado["answer"],
        sources=[SourceItem(**s) for s in resultado["sources"]],
        tokens=resultado["tokens_used"],
        cost_usd=resultado["cost_usd"],
    )


@app.get("/health")
def health() -> dict:
    """Healthcheck: confirma que o índice está carregado e quantos runbooks há."""
    try:
        meta = get_retriever().metadata
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Índice indisponível: {exc}") from exc

    return {
        "status": "ok",
        "runbooks_indexed": meta.get("num_runbooks", 0),
        "chunks_indexed": meta.get("num_chunks", 0),
        "index_built_at": meta.get("index_built_at"),
        "model": config.CLAUDE_MODEL,
    }


@app.get("/runbooks")
def list_runbooks() -> dict:
    """Lista os runbooks indexados e quantos chunks cada um gerou."""
    meta = get_retriever().metadata
    chunks = meta.get("chunks", [])

    # Conta chunks por arquivo.
    contagem: dict[str, int] = {}
    for c in chunks:
        contagem[c["source_file"]] = contagem.get(c["source_file"], 0) + 1

    runbooks = [
        {"file": arquivo, "chunks": contagem.get(arquivo, 0)}
        for arquivo in meta.get("runbooks_indexed", [])
    ]
    return {"count": len(runbooks), "runbooks": runbooks}


# ----- Frontend estático -----

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve a página principal do frontend."""
    return FileResponse(STATIC_DIR / "index.html")


# Monta os demais arquivos estáticos (CSS/JS) em /static.
# Feito por último para não sobrescrever as rotas de API definidas acima.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
