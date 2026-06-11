"""Testes do motor RAG: construção do prompt e parsing da resposta da Claude.

Usamos um retriever falso e um cliente Anthropic falso para não depender do índice
real nem fazer chamadas pagas à API.
"""
from types import SimpleNamespace

import pytest

from src import config
from src import rag as rag_mod


# ----- build_prompt -----

def test_build_prompt_inclui_contexto_pergunta_e_instrucao():
    chunks = [
        {"source_file": "alb-502-errors.md", "chunk_text": "Erro 502 ocorre quando..."},
        {"source_file": "ecs-deployment.md", "chunk_text": "Rollback aponta a revisão..."},
    ]
    prompt = rag_mod.build_prompt("Como resolver 502?", chunks)

    # Contém os textos dos chunks.
    assert "Erro 502 ocorre quando" in prompt
    assert "Rollback aponta a revisão" in prompt
    # Cita as fontes de cada trecho.
    assert "alb-502-errors.md" in prompt
    assert "ecs-deployment.md" in prompt
    # Inclui a pergunta.
    assert "Como resolver 502?" in prompt
    # Inclui a instrução de responder só com base no contexto.
    assert "APENAS no contexto" in prompt
    assert "não encontrou nos runbooks" in prompt


# ----- Fakes para o RAGEngine -----

class FakeRetriever:
    """Retriever falso que devolve chunks pré-definidos."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.ultima_query = None
        self.ultimo_top_k = None

    def search(self, query, top_k=3):
        self.ultima_query = query
        self.ultimo_top_k = top_k
        return self._chunks


class FakeMessages:
    """Simula client.messages com um create() que retorna resposta controlada."""

    def __init__(self, texto, input_tokens, output_tokens):
        self._texto = texto
        self._input = input_tokens
        self._output = output_tokens
        self.chamada_kwargs = None

    def create(self, **kwargs):
        self.chamada_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._texto)],
            usage=SimpleNamespace(input_tokens=self._input, output_tokens=self._output),
        )


class FakeClient:
    def __init__(self, texto="Resposta de teste.", input_tokens=100, output_tokens=50):
        self.messages = FakeMessages(texto, input_tokens, output_tokens)


def test_retrieve_and_generate_monta_resposta_completa():
    chunks = [
        {"source_file": "ecs-deployment.md", "chunk_text": "Para rollback, aponte a revisão anterior.", "score": 0.9},
    ]
    retriever = FakeRetriever(chunks)
    client = FakeClient(texto="Use update-service apontando a revisão anterior.",
                        input_tokens=200, output_tokens=80)
    engine = rag_mod.RAGEngine(retriever=retriever, client=client)

    resultado = engine.retrieve_and_generate("Como fazer rollback ECS?", top_k=3)

    # Resposta vem do cliente falso.
    assert resultado["answer"] == "Use update-service apontando a revisão anterior."
    # Fontes derivam dos chunks recuperados.
    assert resultado["sources"] == [{"file": "ecs-deployment.md", "score": 0.9}]
    # Tokens somados.
    assert resultado["tokens_used"] == 280
    # Custo calculado pela função de config.
    assert resultado["cost_usd"] == config.estimate_cost_usd(200, 80)
    # O top_k foi repassado ao retriever.
    assert retriever.ultimo_top_k == 3


def test_retrieve_and_generate_usa_modelo_e_prompt_corretos():
    chunks = [{"source_file": "a.md", "chunk_text": "contexto relevante", "score": 0.5}]
    client = FakeClient()
    engine = rag_mod.RAGEngine(retriever=FakeRetriever(chunks), client=client)

    engine.retrieve_and_generate("pergunta qualquer")

    kwargs = client.messages.chamada_kwargs
    # Usa o modelo configurado.
    assert kwargs["model"] == config.CLAUDE_MODEL
    # O prompt do usuário contém o contexto recuperado.
    conteudo_usuario = kwargs["messages"][0]["content"]
    assert "contexto relevante" in conteudo_usuario
    # Há um system prompt definido.
    assert kwargs["system"]


def test_retrieve_and_generate_sem_chunks_nao_chama_api():
    """Sem chunks recuperados, não deve gastar chamada à API."""
    client = FakeClient()
    engine = rag_mod.RAGEngine(retriever=FakeRetriever([]), client=client)

    resultado = engine.retrieve_and_generate("pergunta sem contexto")

    assert resultado["sources"] == []
    assert resultado["tokens_used"] == 0
    assert resultado["cost_usd"] == 0.0
    # create() nunca foi chamado.
    assert client.messages.chamada_kwargs is None


def test_estimate_cost_usd_calculo():
    """Custo = input/1M * preço_in + output/1M * preço_out."""
    custo = config.estimate_cost_usd(1_000_000, 1_000_000)
    esperado = config.PRICE_INPUT_PER_1M + config.PRICE_OUTPUT_PER_1M
    assert custo == pytest.approx(esperado)
