"""Motor RAG (Retrieval-Augmented Generation).

Junta o retriever (busca semântica no FAISS) com a Claude: recupera os chunks
mais relevantes, monta um prompt com esse contexto e pede para a Claude responder
em português, citando as fontes.
"""
from __future__ import annotations

import os

from anthropic import Anthropic

try:
    from . import config
    from .retriever import Retriever
except ImportError:  # pragma: no cover
    import config
    from retriever import Retriever


# Instrução de sistema: define o comportamento da Claude como assistente de runbooks.
SYSTEM_PROMPT = (
    "Você é um assistente técnico de plantão (on-call) que responde dúvidas sobre "
    "runbooks de infraestrutura AWS. Responda sempre em português brasileiro, de "
    "forma objetiva e prática, usando APENAS o contexto fornecido."
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    """Monta o prompt do usuário com o contexto dos chunks recuperados.

    Cada chunk entra rotulado com seu arquivo de origem, ajudando a Claude a
    fundamentar a resposta e a citar a fonte correta.
    """
    blocos_contexto = []
    for i, chunk in enumerate(chunks, start=1):
        blocos_contexto.append(
            f"[Trecho {i} — fonte: {chunk['source_file']}]\n{chunk['chunk_text']}"
        )
    contexto = "\n\n".join(blocos_contexto)

    return (
        f"Contexto dos runbooks:\n{contexto}\n\n\n"
        f"Pergunta: {question}\n\n\n"
        f"Responda em português brasileiro baseado APENAS no contexto acima.\n"
        f"Se a resposta não estiver no contexto, diga que não encontrou nos runbooks."
    )


class RAGEngine:
    """Orquestra busca + geração com a Claude, reaproveitando retriever e cliente."""

    def __init__(self, retriever: Retriever | None = None, client: Anthropic | None = None) -> None:
        # Permite injetar retriever/cliente nos testes; caso contrário, cria os reais.
        self.retriever = retriever or Retriever()
        if client is not None:
            self.client = client
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY não definida. Configure no arquivo .env."
                )
            self.client = Anthropic(api_key=api_key)

    def retrieve_and_generate(self, question: str, top_k: int = config.DEFAULT_TOP_K) -> dict:
        """Executa o fluxo RAG completo e retorna a resposta com fontes e custo.

        Retorna: {answer, sources: [{file, score}], tokens_used, cost_usd}.
        """
        # 1. Recupera os chunks mais relevantes no índice FAISS.
        chunks = self.retriever.search(question, top_k=top_k)

        # Sem nenhum chunk, evita gastar uma chamada à API.
        if not chunks:
            return {
                "answer": "Não encontrei informações sobre isso nos runbooks indexados.",
                "sources": [],
                "tokens_used": 0,
                "cost_usd": 0.0,
            }

        # 2. Monta o prompt com o contexto recuperado.
        prompt = build_prompt(question, chunks)

        # 3. Chama a Claude.
        resposta = self.client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # 4. Extrai texto, tokens e calcula o custo estimado.
        texto = "".join(
            bloco.text for bloco in resposta.content if bloco.type == "text"
        ).strip()

        input_tokens = resposta.usage.input_tokens
        output_tokens = resposta.usage.output_tokens
        custo = config.estimate_cost_usd(input_tokens, output_tokens)

        # Fontes deduplicadas (o retriever já garante um chunk por arquivo).
        sources = [
            {"file": c["source_file"], "score": round(c["score"], 4)}
            for c in chunks
        ]

        return {
            "answer": texto,
            "sources": sources,
            "tokens_used": input_tokens + output_tokens,
            "cost_usd": custo,
        }


def retrieve_and_generate(question: str, top_k: int = config.DEFAULT_TOP_K) -> dict:
    """Função de conveniência: cria um RAGEngine e responde uma pergunta.

    Útil para uso pontual no CLI ou na API sem gerenciar o ciclo de vida do engine.
    """
    engine = RAGEngine()
    return engine.retrieve_and_generate(question, top_k=top_k)
