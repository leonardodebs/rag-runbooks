"""Recuperador (retriever) sobre o índice FAISS.

Carrega o índice e os metadados, transforma uma pergunta em vetor e busca os
chunks mais relevantes. Faz deduplicação por arquivo de origem, mantendo apenas
o chunk de maior score (menor distância) de cada runbook.
"""
from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

try:
    from . import config
except ImportError:  # pragma: no cover
    import config


class Retriever:
    """Encapsula o índice FAISS e o modelo de embeddings para fazer buscas."""

    def __init__(self, index_dir: Path | str = config.INDEX_DIR) -> None:
        self.index_dir = Path(index_dir)
        caminho_faiss = self.index_dir / config.FAISS_INDEX_FILE
        caminho_metadata = self.index_dir / config.METADATA_FILE

        if not caminho_faiss.exists() or not caminho_metadata.exists():
            raise FileNotFoundError(
                f"Índice não encontrado em {self.index_dir}. "
                f"Rode o indexador primeiro (make index)."
            )

        # Carrega o índice FAISS e o JSON de metadados.
        self.index = faiss.read_index(str(caminho_faiss))
        self.metadata = json.loads(caminho_metadata.read_text(encoding="utf-8"))
        self.chunks: list[dict] = self.metadata["chunks"]

        # Carrega o mesmo modelo de embeddings usado na indexação.
        nome_modelo = self.metadata.get("embedding_model", config.EMBEDDING_MODEL)
        self.model = SentenceTransformer(nome_modelo, device=config.EMBEDDING_DEVICE)

    def embed_query(self, text: str) -> np.ndarray:
        """Converte um texto de pergunta em um vetor float32 (1, dim) para o FAISS."""
        vetor = self.model.encode([text], convert_to_numpy=True, show_progress_bar=False)
        return vetor.astype("float32")

    def search(self, query: str, top_k: int = config.DEFAULT_TOP_K) -> list[dict]:
        """Busca os chunks mais relevantes para a pergunta.

        Retorna uma lista de dicts com chunk_text, source_file, score e chunk_id.
        O `score` é uma similaridade derivada da distância L2 (quanto maior, melhor),
        calculada como 1 / (1 + distância).

        Aplica deduplicação: se o mesmo source_file aparece mais de uma vez, mantém
        apenas a ocorrência de maior score.
        """
        if top_k <= 0:
            return []

        vetor = self.embed_query(query)

        # Busca mais candidatos que top_k para que, após a deduplicação por arquivo,
        # ainda sobrem resultados suficientes.
        n_candidatos = min(top_k * 5, self.index.ntotal)
        distancias, indices = self.index.search(vetor, n_candidatos)

        melhores_por_arquivo: dict[str, dict] = {}
        for distancia, idx in zip(distancias[0], indices[0]):
            # O FAISS retorna -1 para posições vazias quando há menos vetores que o pedido.
            if idx < 0:
                continue
            registro = self.chunks[idx]
            score = float(1.0 / (1.0 + distancia))
            resultado = {
                "chunk_id": registro["chunk_id"],
                "source_file": registro["source_file"],
                "chunk_text": registro["chunk_text"],
                "score": score,
            }
            arquivo = registro["source_file"]
            # Mantém apenas o de maior score por arquivo (dedup).
            atual = melhores_por_arquivo.get(arquivo)
            if atual is None or score > atual["score"]:
                melhores_por_arquivo[arquivo] = resultado

        # Ordena por score decrescente e corta em top_k.
        ordenados = sorted(
            melhores_por_arquivo.values(),
            key=lambda r: r["score"],
            reverse=True,
        )
        return ordenados[:top_k]
