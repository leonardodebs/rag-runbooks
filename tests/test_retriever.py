"""Testes do retriever: formato dos resultados, top_k e deduplicação por fonte.

Para não depender do modelo real de embeddings (lento) nem de chamadas externas,
construímos um índice FAISS pequeno com vetores controlados e injetamos um modelo
falso que mapeia textos conhecidos para esses vetores.
"""
import json

import faiss
import numpy as np
import pytest

from src import config, indexer
from src import retriever as retriever_mod


class FakeModel:
    """Modelo de embeddings falso: devolve um vetor fixo por texto conhecido."""

    def __init__(self, mapa: dict[str, list[float]]):
        self.mapa = mapa

    def encode(self, textos, convert_to_numpy=True, show_progress_bar=False):
        vetores = [self.mapa[t] for t in textos]
        return np.array(vetores, dtype="float32")


@pytest.fixture
def index_dir(tmp_path):
    """Cria um índice FAISS de teste com 4 chunks de 2 dimensões.

    Dois chunks pertencem ao mesmo arquivo (a.md) para exercitar a deduplicação.
    """
    registros = [
        {"chunk_id": 0, "source_file": "a.md", "chunk_index": 0, "chunk_text": "chunk-a0"},
        {"chunk_id": 1, "source_file": "a.md", "chunk_index": 1, "chunk_text": "chunk-a1"},
        {"chunk_id": 2, "source_file": "b.md", "chunk_index": 0, "chunk_text": "chunk-b0"},
        {"chunk_id": 3, "source_file": "c.md", "chunk_index": 0, "chunk_text": "chunk-c0"},
    ]
    # Vetores posicionados em pontos distintos do plano 2D.
    embeddings = np.array([
        [0.0, 0.0],   # a0
        [0.1, 0.0],   # a1 (perto de a0)
        [5.0, 5.0],   # b0
        [9.0, 9.0],   # c0
    ], dtype="float32")

    index = faiss.IndexFlatL2(2)
    index.add(embeddings)
    indexer.save_index(index, registros, tmp_path, tmp_path, 2)
    return tmp_path


@pytest.fixture
def retriever(index_dir, monkeypatch):
    """Instancia o Retriever com um FakeModel no lugar do SentenceTransformer real."""
    # Mapa de query -> vetor, alinhado com os embeddings do índice.
    mapa_query = {
        "perto de a": [0.0, 0.0],
        "perto de b": [5.0, 5.0],
    }
    monkeypatch.setattr(
        retriever_mod, "SentenceTransformer",
        lambda *a, **k: FakeModel(mapa_query),
    )
    return retriever_mod.Retriever(index_dir=index_dir)


def test_search_retorna_formato_correto(retriever):
    resultados = retriever.search("perto de a", top_k=1)
    assert len(resultados) == 1
    r = resultados[0]
    assert set(r.keys()) == {"chunk_id", "source_file", "chunk_text", "score"}
    assert isinstance(r["score"], float)


def test_search_ordena_por_relevancia(retriever):
    """A query 'perto de a' deve trazer a.md como resultado mais relevante."""
    resultados = retriever.search("perto de a", top_k=3)
    assert resultados[0]["source_file"] == "a.md"
    # Scores em ordem decrescente.
    scores = [r["score"] for r in resultados]
    assert scores == sorted(scores, reverse=True)


def test_search_deduplica_por_arquivo(retriever):
    """Mesmo com dois chunks de a.md próximos, só um deve aparecer (o de maior score)."""
    resultados = retriever.search("perto de a", top_k=4)
    arquivos = [r["source_file"] for r in resultados]
    # Não pode haver arquivo repetido.
    assert len(arquivos) == len(set(arquivos))
    # a.md aparece uma única vez.
    assert arquivos.count("a.md") == 1


def test_search_respeita_top_k(retriever):
    resultados = retriever.search("perto de b", top_k=2)
    assert len(resultados) <= 2


def test_search_top_k_zero_retorna_vazio(retriever):
    assert retriever.search("perto de a", top_k=0) == []


def test_retriever_sem_indice_levanta_erro(tmp_path):
    with pytest.raises(FileNotFoundError):
        retriever_mod.Retriever(index_dir=tmp_path / "inexistente")


def test_metadata_carregado(retriever):
    """O retriever deve expor os metadados do índice."""
    assert retriever.metadata["num_chunks"] == 4
    assert "a.md" in retriever.metadata["runbooks_indexed"]
