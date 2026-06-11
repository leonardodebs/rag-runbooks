"""Indexador de runbooks.

Lê todos os arquivos .md/.txt de um diretório, quebra cada documento em chunks
com sobreposição, gera embeddings com sentence-transformers, constrói um índice
FAISS (IndexFlatL2) e persiste o índice + os metadados em disco.

Uso:
    python src/indexer.py --runbooks-dir data/runbooks/ --output data/index/
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from sentence_transformers import SentenceTransformer

# Suporta execução tanto como script (`python src/indexer.py`) quanto como
# módulo (`from src import indexer`).
try:
    from . import config
except ImportError:  # pragma: no cover
    import config

console = Console()


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE_WORDS,
    overlap: int = config.CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Quebra um texto em janelas de `chunk_size` palavras com `overlap` de sobreposição.

    A janela desliza de (chunk_size - overlap) palavras por vez, garantindo que o
    contexto nas bordas não se perca entre chunks vizinhos.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser menor que chunk_size")

    palavras = text.split()
    if not palavras:
        return []

    passo = chunk_size - overlap
    chunks: list[str] = []
    for inicio in range(0, len(palavras), passo):
        janela = palavras[inicio:inicio + chunk_size]
        if janela:
            chunks.append(" ".join(janela))
        # Se a janela já alcançou o fim do documento, encerra.
        if inicio + chunk_size >= len(palavras):
            break
    return chunks


def load_runbooks(runbooks_dir: Path) -> list[tuple[str, str]]:
    """Carrega todos os arquivos .md/.txt do diretório.

    Retorna uma lista de tuplas (nome_do_arquivo, conteúdo), ordenada pelo nome
    para tornar a indexação determinística.
    """
    arquivos = sorted(
        p for p in runbooks_dir.iterdir()
        if p.suffix.lower() in {".md", ".txt"}
    )
    documentos: list[tuple[str, str]] = []
    for caminho in arquivos:
        conteudo = caminho.read_text(encoding="utf-8").strip()
        if conteudo:
            documentos.append((caminho.name, conteudo))
    return documentos


def build_chunks(documentos: Iterable[tuple[str, str]]) -> list[dict]:
    """Transforma documentos em uma lista de registros de chunk com metadados.

    Cada registro contém: chunk_id (global), source_file, chunk_index (dentro do
    documento) e o texto do chunk.
    """
    registros: list[dict] = []
    chunk_id = 0
    for nome_arquivo, conteudo in documentos:
        for indice_local, texto_chunk in enumerate(chunk_text(conteudo)):
            registros.append({
                "chunk_id": chunk_id,
                "source_file": nome_arquivo,
                "chunk_index": indice_local,
                "chunk_text": texto_chunk,
            })
            chunk_id += 1
    return registros


def embed_chunks(model: SentenceTransformer, registros: list[dict]) -> np.ndarray:
    """Gera os embeddings dos chunks, exibindo uma barra de progresso com Rich.

    Retorna uma matriz float32 (n_chunks, dim) pronta para o FAISS.
    """
    textos = [r["chunk_text"] for r in registros]
    vetores: list[np.ndarray] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Gerando embeddings"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} chunks"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        tarefa = progress.add_task("embed", total=len(textos))
        # Codifica em lotes para eficiência, atualizando a barra a cada lote.
        tamanho_lote = 32
        for inicio in range(0, len(textos), tamanho_lote):
            lote = textos[inicio:inicio + tamanho_lote]
            emb = model.encode(lote, convert_to_numpy=True, show_progress_bar=False)
            vetores.append(emb)
            progress.update(tarefa, advance=len(lote))

    return np.vstack(vetores).astype("float32")


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """Constrói um índice FAISS IndexFlatL2 (distância euclidiana) e adiciona os vetores."""
    dimensao = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimensao)
    index.add(embeddings)
    return index


def save_index(
    index: faiss.Index,
    registros: list[dict],
    output_dir: Path,
    runbooks_dir: Path,
    embedding_dim: int,
) -> None:
    """Persiste o índice FAISS e o metadata.json no diretório de saída."""
    output_dir.mkdir(parents=True, exist_ok=True)

    caminho_faiss = output_dir / config.FAISS_INDEX_FILE
    faiss.write_index(index, str(caminho_faiss))

    # Lista de arquivos únicos indexados, preservando a ordem.
    arquivos_indexados = sorted({r["source_file"] for r in registros})

    metadata = {
        "embedding_model": config.EMBEDDING_MODEL,
        "embedding_dim": embedding_dim,
        "index_built_at": datetime.now(timezone.utc).isoformat(),
        "runbooks_dir": str(runbooks_dir),
        "num_chunks": len(registros),
        "num_runbooks": len(arquivos_indexados),
        "runbooks_indexed": arquivos_indexados,
        "chunk_size_words": config.CHUNK_SIZE_WORDS,
        "chunk_overlap_words": config.CHUNK_OVERLAP_WORDS,
        # Os chunks ficam alinhados por posição com os vetores do FAISS (chunk_id == índice).
        "chunks": registros,
    }

    caminho_metadata = output_dir / config.METADATA_FILE
    caminho_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_index(runbooks_dir: Path, output_dir: Path) -> dict:
    """Executa o pipeline completo de indexação e retorna um resumo.

    Esta função é reutilizada pelos testes e pelo CLI.
    """
    console.print(f"[bold]Carregando runbooks de:[/bold] {runbooks_dir}")
    documentos = load_runbooks(runbooks_dir)
    if not documentos:
        raise SystemExit(f"Nenhum runbook (.md/.txt) encontrado em {runbooks_dir}")
    console.print(f"  {len(documentos)} runbooks carregados.")

    registros = build_chunks(documentos)
    console.print(f"  {len(registros)} chunks gerados "
                  f"({config.CHUNK_SIZE_WORDS} palavras, "
                  f"{config.CHUNK_OVERLAP_WORDS} de sobreposição).")

    console.print(f"[bold]Carregando modelo de embeddings:[/bold] {config.EMBEDDING_MODEL} "
                  f"(device={config.EMBEDDING_DEVICE})")
    model = SentenceTransformer(config.EMBEDDING_MODEL, device=config.EMBEDDING_DEVICE)

    embeddings = embed_chunks(model, registros)
    console.print(f"  Embeddings: matriz {embeddings.shape}.")

    index = build_faiss_index(embeddings)
    save_index(index, registros, output_dir, runbooks_dir, embeddings.shape[1])

    console.print(f"[bold green]✓ Índice salvo em:[/bold green] {output_dir}")
    return {
        "num_runbooks": len(documentos),
        "num_chunks": len(registros),
        "embedding_dim": embeddings.shape[1],
        "output_dir": str(output_dir),
    }


def main() -> None:
    """Ponto de entrada do CLI do indexador."""
    parser = argparse.ArgumentParser(description="Indexa runbooks em um índice FAISS.")
    parser.add_argument(
        "--runbooks-dir",
        type=Path,
        default=config.RUNBOOKS_DIR,
        help="Diretório com os arquivos .md/.txt dos runbooks.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.INDEX_DIR,
        help="Diretório de saída para o índice FAISS e os metadados.",
    )
    args = parser.parse_args()
    run_index(args.runbooks_dir, args.output)


if __name__ == "__main__":
    main()
