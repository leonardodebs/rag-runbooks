"""Configuração central compartilhada por todo o sistema RAG.

Centraliza caminhos, nome do modelo de embeddings, modelo da Claude e parâmetros
de chunking, para que indexer, retriever, rag e cli usem os mesmos valores.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (se existir) para o ambiente.
load_dotenv()

# Raiz do projeto (dois níveis acima deste arquivo: src/config.py -> projeto/).
ROOT_DIR = Path(__file__).resolve().parent.parent

# Diretórios padrão de runbooks e do índice gerado.
RUNBOOKS_DIR = ROOT_DIR / "data" / "runbooks"
INDEX_DIR = ROOT_DIR / "data" / "index"

# Nomes dos arquivos que compõem o índice persistido.
FAISS_INDEX_FILE = "faiss.index"
METADATA_FILE = "metadata.json"

# Modelo de embeddings local (gratuito, não precisa de API).
# all-MiniLM-L6-v2 gera vetores de 384 dimensões.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Device para os embeddings. Padrão "cpu" — o modelo é pequeno e roda rápido na
# CPU, evitando incompatibilidades de driver/GPU (ex: CUDA em WSL2). Use "cuda"
# apenas se sua GPU for compatível com o build do torch instalado.
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# Modelo da Claude usado para gerar as respostas.
# Obs.: o spec original citava "claude-3-haiku", que está depreciado (sai em
# abr/2026). Usamos o Haiku atual (mesma classe econômica), configurável via .env.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

# Preço do Haiku 4.5 por 1 milhão de tokens (USD), usado para estimar o custo.
# Fonte: tabela de preços da Claude API (input $1 / output $5 por 1M tokens).
PRICE_INPUT_PER_1M = float(os.getenv("PRICE_INPUT_PER_1M", "1.0"))
PRICE_OUTPUT_PER_1M = float(os.getenv("PRICE_OUTPUT_PER_1M", "5.0"))

# Parâmetros de chunking: tamanho da janela e sobreposição, ambos em palavras.
CHUNK_SIZE_WORDS = int(os.getenv("CHUNK_SIZE_WORDS", "300"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "50"))

# Quantidade padrão de chunks recuperados na busca.
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "3"))


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estima o custo em dólares de uma chamada à Claude.

    Multiplica a quantidade de tokens de entrada e saída pelos preços por milhão.
    """
    custo_input = (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    custo_output = (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    return round(custo_input + custo_output, 6)
