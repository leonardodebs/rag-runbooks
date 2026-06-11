# Exemplos de Variáveis de Ambiente — RAG Runbooks

Este documento descreve todas as variáveis de ambiente do sistema, seus valores
padrão e como configurá-las. A configuração é lida pelo `src/config.py` via
`python-dotenv` a partir de um arquivo `.env` na raiz do projeto.

> ⚠️ O `.env` é lido **uma única vez**, na inicialização do processo. Ao alterá-lo,
> **reinicie** a aplicação (CLI, API) para que as mudanças tenham efeito.

---

## Como usar

```bash
# 1. Copie o template versionado
cp .env.example .env

# 2. Edite e preencha pelo menos a ANTHROPIC_API_KEY
#    (as demais têm padrões sensatos)

# 3. Rode normalmente
make index && make web
```

O `.env` está no `.gitignore` — **nunca** comite segredos. Apenas o `.env.example`
(sem valores reais) vai para o repositório.

---

## Variáveis

### Obrigatória

| Variável | Exemplo | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` | Chave da Claude API. Necessária para **gerar respostas** (`/query`, `make query`, `make eval`). Indexação e testes **não** precisam dela. |

### Opcionais (têm valor padrão)

| Variável | Padrão | Descrição |
|---|---|---|
| `CLAUDE_MODEL` | `claude-haiku-4-5` | Modelo da Claude usado na geração. Classe econômica, ideal para Q&A com contexto. |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Modelo de embeddings (sentence-transformers). 384 dimensões, roda local. |
| `EMBEDDING_DEVICE` | `cpu` | Device dos embeddings. Use `cuda` **apenas** se sua GPU for compatível com o torch instalado (em WSL2 normalmente não é — mantenha `cpu`). |
| `CHUNK_SIZE_WORDS` | `300` | Tamanho de cada chunk, em palavras. |
| `CHUNK_OVERLAP_WORDS` | `50` | Sobreposição entre chunks vizinhos, em palavras. Deve ser **menor** que `CHUNK_SIZE_WORDS`. |
| `DEFAULT_TOP_K` | `3` | Quantidade padrão de chunks recuperados por pergunta. |
| `PRICE_INPUT_PER_1M` | `1.0` | Preço (USD) por 1M de tokens de entrada — usado na estimativa de custo. |
| `PRICE_OUTPUT_PER_1M` | `5.0` | Preço (USD) por 1M de tokens de saída — usado na estimativa de custo. |

> Os preços padrão (`1.0` / `5.0`) correspondem ao `claude-haiku-4-5`. Se trocar de
> modelo via `CLAUDE_MODEL`, ajuste-os para manter a estimativa de custo correta.

---

## Template completo (`.env`)

```dotenv
# === Obrigatória ===
# Chave da Claude API. Obtenha em https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === Modelos (opcionais) ===
# Modelo da Claude para gerar as respostas.
CLAUDE_MODEL=claude-haiku-4-5

# Modelo de embeddings local (384 dimensões, gratuito).
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Device dos embeddings: cpu (padrão, seguro) ou cuda (só com GPU compatível).
EMBEDDING_DEVICE=cpu

# === Chunking e busca (opcionais) ===
CHUNK_SIZE_WORDS=300
CHUNK_OVERLAP_WORDS=50
DEFAULT_TOP_K=3

# === Preços para estimativa de custo (opcionais) ===
# Devem corresponder ao CLAUDE_MODEL escolhido (padrão: Haiku 4.5).
PRICE_INPUT_PER_1M=1.0
PRICE_OUTPUT_PER_1M=5.0
```

---

## Notas de segurança

- **Nunca** comite o `.env` (já protegido pelo `.gitignore`).
- Em produção, prefira um gerenciador de segredos (AWS Secrets Manager, Vault) em
  vez de arquivo em disco — ver "Caminho para produção" no README.
- A `ANTHROPIC_API_KEY` dá acesso pago à sua conta; rotacione-a se for exposta.

---

## Diferenças por ambiente

| Variável | Desenvolvimento | Produção (sugestão) |
|---|---|---|
| `ANTHROPIC_API_KEY` | `.env` local | Secrets Manager / variável injetada |
| `EMBEDDING_DEVICE` | `cpu` | `cuda` se houver GPU compatível, senão `cpu` |
| `CLAUDE_MODEL` | `claude-haiku-4-5` | igual, ou Sonnet para respostas mais sofisticadas |
| `DEFAULT_TOP_K` | `3` | ajustar conforme avaliação (precision@k) |

Ver também: [ARQUITETURA.md](ARQUITETURA.md) e [RUNBOOK.md](RUNBOOK.md).
