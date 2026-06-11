# Runbook Operacional — RAG Runbooks

Procedimentos operacionais e guia de troubleshooting do **próprio sistema** RAG.
Use este documento para instalar, operar, diagnosticar e recuperar o serviço.

> Meta: este é o "runbook do sistema de runbooks" 🙂

---

## 1. Setup inicial

### Pré-requisitos
- Python 3.12
- ~500 MB de disco (modelos de embeddings baixados na 1ª execução)
- `ANTHROPIC_API_KEY` (apenas para gerar respostas)

### Passos
```bash
# 1. Cria o venv e instala dependências
make setup

# 2. Configura a chave da Claude
cp .env.example .env          # edite e preencha ANTHROPIC_API_KEY

# 3. Indexa os runbooks (gera data/index/)
make index

# 4. Valida
make test                     # 20 testes, não precisa de API key
make query Q="Como resolver erro 502 no ALB?"
```

---

## 2. Operações do dia a dia

| Tarefa | Comando |
|---|---|
| (Re)indexar runbooks | `make index` |
| Pergunta única (CLI) | `make query Q="sua pergunta"` |
| Pergunta com top-k custom | `make query TOP_K=5 Q="..."` |
| Modo interativo | `.venv/bin/python src/cli.py --interactive` |
| Subir API + frontend | `make web` (http://localhost:8000) |
| Rodar avaliação | `make eval` |
| Rodar testes | `make test` |
| Limpar tudo (venv, índice, cache) | `make clean` |

### Quando re-indexar
Rode `make index` sempre que:
- adicionar, remover ou editar um arquivo em `data/runbooks/`;
- mudar `CHUNK_SIZE_WORDS`, `CHUNK_OVERLAP_WORDS` ou `EMBEDDING_MODEL`.

Após re-indexar, **reinicie a API** (`make web`) para recarregar o índice em memória.

### Subir/derrubar a API
```bash
# Subir
make web

# Derrubar (em outro terminal)
pkill -f "uvicorn src.api:app"
```

### Verificar saúde
```bash
curl -s http://localhost:8000/health | python -m json.tool
# status "ok" + runbooks_indexed + index_built_at
```

---

## 3. Troubleshooting

### 3.1 `ANTHROPIC_API_KEY não definida`
**Sintoma:** CLI/frontend retorna esse erro ao perguntar.
**Causas e correções:**
1. `.env` não existe → `cp .env.example .env` e preencha a chave.
2. Chave preenchida **após** subir o servidor → o `.env` é lido na inicialização;
   **reinicie** (`pkill -f uvicorn` e `make web`).
3. Chave malformada → deve começar com `sk-ant-`.

Verifique (sem revelar o valor):
```bash
grep -q "^ANTHROPIC_API_KEY=sk-" .env && echo "ok" || echo "ausente/invalida"
```

### 3.2 `Índice não encontrado` / `/health` retorna 503
**Sintoma:** `FileNotFoundError` no `Retriever` ou healthcheck falhando.
**Causa:** o índice ainda não foi gerado (ou foi limpo com `make clean`).
**Correção:**
```bash
make index
ls -la data/index/      # deve ter faiss.index e metadata.json
```

### 3.3 `CUDA error: no kernel image is available`
**Sintoma:** a indexação quebra ao carregar o modelo de embeddings.
**Causa:** o torch instalado é build CUDA, mas a GPU (ex: em WSL2) não é compatível.
**Correção:** force CPU (já é o padrão). Garanta:
```bash
# no .env
EMBEDDING_DEVICE=cpu
```
Se persistir, exporte na sessão: `export EMBEDDING_DEVICE=cpu` antes de `make index`.

### 3.4 Resposta "não encontrei nos runbooks"
**Sintoma:** o sistema não acha contexto para a pergunta.
**Causas e correções:**
1. O assunto realmente não está nos runbooks → comportamento esperado (anti-alucinação).
2. Pergunta muito vaga → reformule com termos técnicos.
3. Aumente o `top-k`: `make query TOP_K=5 Q="..."`.
4. Confirme que o índice tem os documentos: `curl localhost:8000/runbooks`.

### 3.5 Frontend carrega mas a sidebar mostra "Índice indisponível"
**Causa:** a API está no ar, mas o índice não foi gerado.
**Correção:** `make index`, depois recarregue a página (F5).

### 3.6 Download lento / `unauthenticated requests to the HF Hub`
**Sintoma:** aviso ao baixar o modelo de embeddings.
**Impacto:** apenas um warning; o download funciona (mais lento sob rate limit).
**Correção opcional:** exporte um `HF_TOKEN` para limites maiores.

### 3.7 Porta 8000 já em uso
**Sintoma:** `Address already in use` ao subir a API.
**Correção:**
```bash
pkill -f "uvicorn src.api:app"     # mata instância anterior
# ou suba em outra porta:
.venv/bin/uvicorn src.api:app --port 8001
```

### 3.8 Testes falhando após mudanças
**Correção:** rode com saída detalhada e investigue o primeiro erro:
```bash
.venv/bin/python -m pytest -v
```
Lembre: os testes usam mocks e **não** chamam a Claude nem dependem do índice real.

---

## 4. Verificação de integridade (health checks)

Checklist rápido para confirmar que o sistema está saudável:

```bash
# 1. Índice existe e é consistente
test -f data/index/faiss.index && test -f data/index/metadata.json && echo "índice ok"

# 2. Testes passam
make test

# 3. API responde
curl -s http://localhost:8000/health | grep -q '"status":"ok"' && echo "api ok"

# 4. Recuperação funciona (sem custo de API)
.venv/bin/python -c "from src.retriever import Retriever; \
print('recuperação ok:', Retriever().search('rollback ECS', top_k=3)[0]['source_file'])"
```

---

## 5. Avaliação de qualidade

Para medir a qualidade do sistema (precision@k + cobertura de keywords):
```bash
make eval
```
Métricas de referência (baseline já alcançado):
- **Precision@3:** 100% (10/10) — fonte correta sempre recuperada.
- **Cobertura de keywords:** ~85% — respostas fiéis ao contexto.
- **Custo:** ~US$ 0,036 nas 10 perguntas (Haiku 4.5).

Se a precision@k cair após adicionar runbooks, considere ajustar o chunking ou o
`top_k`, e re-rodar a avaliação.

---

## 6. Procedimento de recuperação (reset completo)

Se o sistema entrar em estado inconsistente:
```bash
# 1. Limpa venv, índice e caches
make clean

# 2. Reinstala do zero
make setup

# 3. Reindexa
make index

# 4. Valida
make test && make query Q="Como resolver erro 502 no ALB?"
```

---

## 7. Escalonamento

- **Problema de dependências/ambiente:** ver [VARIAVEIS-DE-AMBIENTE.md](VARIAVEIS-DE-AMBIENTE.md).
- **Dúvida de design/fluxo:** ver [ARQUITETURA.md](ARQUITETURA.md).
- **Erro persistente da Claude API (5xx, rate limit):** verifique o status da
  Anthropic e o saldo/limite da conta; o custo por chamada é logado na resposta.
