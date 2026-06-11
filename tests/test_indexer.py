"""Testes do indexador: chunking, formato dos embeddings e criação do índice FAISS."""
import numpy as np
import pytest

from src import indexer


# ----- Chunking -----

def test_chunk_text_respeita_tamanho_e_overlap():
    """Chunks devem ter no máximo chunk_size palavras e sobrepor corretamente."""
    palavras = [f"p{i}" for i in range(700)]
    texto = " ".join(palavras)

    chunks = indexer.chunk_text(texto, chunk_size=300, overlap=50)

    # Com passo de 250 (300-50) sobre 700 palavras: chunks em 0, 250, 500.
    assert len(chunks) == 3
    # Cada chunk tem no máximo 300 palavras.
    for c in chunks:
        assert len(c.split()) <= 300
    # O primeiro chunk tem exatamente 300 palavras.
    assert len(chunks[0].split()) == 300


def test_chunk_text_overlap_real():
    """As últimas palavras de um chunk devem reaparecer no início do próximo."""
    palavras = [f"w{i}" for i in range(300)]
    texto = " ".join(palavras)
    chunks = indexer.chunk_text(texto, chunk_size=100, overlap=20)

    primeiro = chunks[0].split()
    segundo = chunks[1].split()
    # As 20 últimas do primeiro chunk == 20 primeiras do segundo (sobreposição).
    assert primeiro[-20:] == segundo[:20]


def test_chunk_text_vazio_retorna_lista_vazia():
    assert indexer.chunk_text("") == []
    assert indexer.chunk_text("   ") == []


def test_chunk_text_overlap_invalido_levanta_erro():
    with pytest.raises(ValueError):
        indexer.chunk_text("a b c", chunk_size=10, overlap=10)


def test_chunk_text_documento_curto_vira_um_chunk():
    chunks = indexer.chunk_text("apenas tres palavras", chunk_size=300, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "apenas tres palavras"


# ----- build_chunks -----

def test_build_chunks_gera_ids_sequenciais_e_metadados():
    documentos = [
        ("a.md", " ".join(f"x{i}" for i in range(400))),
        ("b.md", "texto curto aqui"),
    ]
    registros = indexer.build_chunks(documentos)

    # chunk_id deve ser sequencial e global.
    ids = [r["chunk_id"] for r in registros]
    assert ids == list(range(len(registros)))

    # Cada registro tem os campos esperados.
    for r in registros:
        assert {"chunk_id", "source_file", "chunk_index", "chunk_text"} <= r.keys()

    # O documento curto gera exatamente 1 chunk.
    chunks_b = [r for r in registros if r["source_file"] == "b.md"]
    assert len(chunks_b) == 1


# ----- Embeddings + FAISS -----

@pytest.fixture(scope="module")
def fake_embeddings():
    """Matriz de embeddings sintética (5 vetores, 8 dimensões) em float32."""
    rng = np.random.default_rng(42)
    return rng.random((5, 8)).astype("float32")


def test_build_faiss_index_formato_e_busca(fake_embeddings):
    """O índice FAISS deve indexar todos os vetores e responder buscas."""
    index = indexer.build_faiss_index(fake_embeddings)

    # Todos os vetores foram adicionados.
    assert index.ntotal == 5
    # A dimensão bate com a dos embeddings.
    assert index.d == 8

    # Buscar pelo próprio vetor 0 deve retorná-lo como mais próximo (distância ~0).
    distancias, indices = index.search(fake_embeddings[:1], 1)
    assert indices[0][0] == 0
    assert distancias[0][0] == pytest.approx(0.0, abs=1e-4)


def test_save_index_persiste_arquivos(tmp_path, fake_embeddings):
    """save_index deve gravar faiss.index e metadata.json com o conteúdo certo."""
    import json
    from src import config

    registros = [
        {"chunk_id": i, "source_file": "a.md", "chunk_index": i, "chunk_text": f"t{i}"}
        for i in range(5)
    ]
    index = indexer.build_faiss_index(fake_embeddings)

    indexer.save_index(index, registros, tmp_path, tmp_path, fake_embeddings.shape[1])

    assert (tmp_path / config.FAISS_INDEX_FILE).exists()
    meta_path = tmp_path / config.METADATA_FILE
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["num_chunks"] == 5
    assert meta["num_runbooks"] == 1
    assert meta["embedding_dim"] == 8
    assert len(meta["chunks"]) == 5
