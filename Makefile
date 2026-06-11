# Makefile do sistema RAG de runbooks
# Usa um virtualenv local em .venv para isolar as dependências.

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Pergunta padrão usada por `make query` quando Q não é informado.
Q ?= Como resolver erro 502 no ALB?
TOP_K ?= 3

.PHONY: help setup install index query api web eval test clean

help:  ## Mostra esta ajuda
	@echo "Alvos disponíveis:"
	@echo "  make setup    - cria o venv e instala as dependências"
	@echo "  make index    - indexa os runbooks em data/index/"
	@echo "  make query Q=\"sua pergunta\"  - pergunta ao RAG"
	@echo "  make api      - sobe a API + frontend web em http://localhost:8000"
	@echo "  make web      - alias de 'make api' (abre o frontend)"
	@echo "  make eval     - roda a avaliação automática"
	@echo "  make test     - roda os testes (não precisa de API key)"
	@echo "  make clean    - remove venv, índice e caches"

$(VENV):  ## Cria o virtualenv
	python3 -m venv $(VENV)

setup: $(VENV) install  ## Cria o venv e instala dependências

install: $(VENV)  ## Instala as dependências no venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

index:  ## Indexa os runbooks (gera data/index/)
	$(PY) src/indexer.py --runbooks-dir data/runbooks/ --output data/index/

query:  ## Pergunta ao RAG: make query Q="sua pergunta"
	$(PY) src/cli.py --top-k $(TOP_K) "$(Q)"

api web:  ## Sobe a API REST + frontend web em http://localhost:8000
	$(VENV)/bin/uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

eval:  ## Roda a avaliação automática (consome a Claude API)
	$(PY) src/eval.py

test:  ## Roda os testes unitários
	$(PY) -m pytest

clean:  ## Limpa venv, índice e caches
	rm -rf $(VENV) data/index .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
