# Documentação de Arquitetura — RAG Runbooks

Este documento descreve em detalhe a arquitetura técnica do sistema RAG de
runbooks: componentes, fluxo de dados, decisões de design e pontos de extensão.

---

## 1. Visão geral

O sistema implementa o padrão **RAG (Retrieval-Augmented Generation)**: a resposta
de uma LLM é fundamentada em trechos recuperados de uma base de documentos própria,
em vez de depender apenas do conhecimento paramétrico do modelo. Isso reduz
alucinação e torna as respostas rastreáveis até a fonte.

O sistema se divide em dois fluxos:

- **Indexação (offline, executada sob demanda):** transforma os runbooks em um
  índice vetorial pesquisável.
- **Consulta (online, por pergunta):** recupera trechos relevantes e gera a
  resposta com a Claude.

```
INDEXAÇÃO (offline)
  runbooks/*.md → chunking → embeddings → FAISS IndexFlatL2 + metadata.json

CONSULTA (online)
  pergunta → embedding → busca FAISS (top-k) → dedup → prompt → Claude → resposta
```

---

## 2. Componentes

| Módulo | Arquivo | Responsabilidade |
|---|---|---|
| Configuração | `src/config.py` | Caminhos, modelos, preços, parâmetros de chunking; carrega `.env`. |
| Indexador | `src/indexer.py` | Lê documentos, faz chunking, gera embeddings, constrói e persiste o índice FAISS. |
| Recuperador | `src/retriever.py` | Carrega o índice, vetoriza a query, busca e deduplica resultados. |
| Motor RAG | `src/rag.py` | Orquestra recuperação + montagem de prompt + chamada à Claude. |
| CLI | `src/cli.py` | Interface de terminal (pergunta única, modo interativo, top-k). |
| API REST | `src/api.py` | Endpoints HTTP (FastAPI) + serve o frontend estático. |
| Frontend | `web/static/` | UI web (HTML/CSS/JS) consumindo a API. |
| Avaliação | `src/eval.py` | Mede precision@k e cobertura de keywords sobre um conjunto de teste. |

### Diagrama de dependências

```
config.py  ◄── indexer.py
   ▲            ▲
   │            │
   ├──── retriever.py ◄── rag.py ◄── cli.py
   │                         ▲   ◄── api.py ◄── web/static
   └──────────────────── eval.py
```

`config.py` é a base; nenhum módulo depende de cima para baixo de forma circular.

---

## 3. Fluxo de indexação (detalhado)

1. **Carga** (`load_runbooks`): lê todos os `.md`/`.txt` do diretório, ordenados por
   nome (indexação determinística).
2. **Chunking** (`chunk_text`): janela deslizante de `CHUNK_SIZE_WORDS` (300)
   palavras com `CHUNK_OVERLAP_WORDS` (50) de sobreposição. O passo é
   `300 - 50 = 250` palavras. A sobreposição evita cortar uma instrução ao meio na
   fronteira entre chunks.
3. **Metadados** (`build_chunks`): cada chunk vira um registro
   `{chunk_id, source_file, chunk_index, chunk_text}`. O `chunk_id` é global e
   sequencial — **alinhado por posição** com os vetores no FAISS.
4. **Embeddings** (`embed_chunks`): `sentence-transformers` (`all-MiniLM-L6-v2`,
   384 dimensões) codifica os textos em lotes de 32, com barra de progresso (Rich).
5. **Índice** (`build_faiss_index`): `faiss.IndexFlatL2` (distância euclidiana,
   busca exata).
6. **Persistência** (`save_index`): grava `faiss.index` (binário FAISS) e
   `metadata.json` (modelo, dimensão, data, lista de runbooks e todos os chunks).

> **Invariante crítica:** a ordem dos chunks no `metadata.json` é idêntica à ordem
> dos vetores no índice FAISS. O `retriever` usa o índice retornado pelo FAISS
> diretamente como posição na lista de chunks.

---

## 4. Fluxo de consulta (detalhado)

1. **Embedding da query** (`Retriever.embed_query`): mesma família de modelo usada
   na indexação (lida do `metadata.json` para garantir compatibilidade).
2. **Busca** (`Retriever.search`): pede ao FAISS `top_k * 5` candidatos para sobrar
   margem após a deduplicação.
3. **Score**: a distância L2 é convertida em similaridade por
   `score = 1 / (1 + distância)` — quanto maior, mais relevante (faixa 0–1).
4. **Deduplicação por arquivo**: se o mesmo `source_file` aparece em mais de um
   chunk, mantém apenas o de maior score. Isso garante **diversidade de fontes** —
   3 runbooks distintos em vez de 3 trechos do mesmo.
5. **Montagem do prompt** (`rag.build_prompt`): cada chunk entra rotulado com a
   fonte; ao final, a pergunta e a instrução de responder *apenas* com base no
   contexto.
6. **Geração** (`RAGEngine.retrieve_and_generate`): chama a Claude
   (`CLAUDE_MODEL`) com um `system` prompt definindo o papel de assistente de
   plantão.
7. **Resposta**: extrai o texto, soma os tokens (`usage.input_tokens +
   output_tokens`), estima o custo (`config.estimate_cost_usd`) e devolve
   `{answer, sources, tokens_used, cost_usd}`.

Curto-circuito: se a busca não retornar nenhum chunk, o engine devolve uma resposta
padrão **sem chamar a API** (economiza custo).

---

## 5. Decisões de design

| Decisão | Alternativa | Por que esta escolha |
|---|---|---|
| Embeddings locais (`all-MiniLM-L6-v2`) | API de embeddings (OpenAI) | Gratuito, offline, sem latência/custo de rede na indexação. |
| FAISS `IndexFlatL2` | Índice aproximado (IVF/HNSW) | Busca exata; para 16 chunks é instantâneo. Trocar é trivial ao escalar. |
| Chunking 300/50 palavras | Chunk por parágrafo/sentença | Equilíbrio entre contexto suficiente e granularidade de busca. |
| Dedup por arquivo | Trazer top-k chunks crus | Diversidade de fontes na resposta. |
| `device="cpu"` nos embeddings | GPU (CUDA) | Modelo pequeno roda rápido na CPU e evita incompatibilidade de driver (WSL2). |
| `claude-haiku-4-5` | `claude-3-haiku` (do spec) | O modelo do spec está depreciado (sai em abr/2026); Haiku atual é a mesma classe econômica. |
| Frontend servido pela API | Servidor estático separado | Um único processo, sem CORS, deploy mais simples. |

---

## 6. Contratos de dados

### `metadata.json`
```jsonc
{
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "index_built_at": "2026-06-11T02:36:02Z",  // ISO 8601 UTC
  "num_chunks": 16,
  "num_runbooks": 8,
  "runbooks_indexed": ["alb-502-errors.md", ...],
  "chunk_size_words": 300,
  "chunk_overlap_words": 50,
  "chunks": [ { "chunk_id": 0, "source_file": "...", "chunk_index": 0, "chunk_text": "..." }, ... ]
}
```

### Resposta de `/query`
```jsonc
{
  "answer": "texto da resposta",
  "sources": [ { "file": "ecs-deployment.md", "score": 0.585 } ],
  "tokens": 1963,
  "cost_usd": 0.002907
}
```

---

## 7. API REST

| Método | Rota | Descrição | Precisa de API key? |
|---|---|---|---|
| `POST` | `/query` | Responde uma pergunta (RAG completo). | Sim (chama a Claude) |
| `GET` | `/health` | Status do índice e do serviço. | Não |
| `GET` | `/runbooks` | Lista runbooks indexados + nº de chunks. | Não |
| `GET` | `/` | Frontend web (`index.html`). | Não |
| `GET` | `/static/*` | CSS/JS do frontend. | Não |
| `GET` | `/docs` | Documentação OpenAPI (Swagger UI). | Não |

O `RAGEngine` e o `Retriever` são criados via `@lru_cache` — instanciados uma vez
e reusados entre requisições (o índice e o modelo carregam só na primeira chamada).

---

## 8. Pontos de extensão

- **Trocar o banco vetorial:** isolar o `Retriever` atrás de uma interface e
  implementar uma versão pgvector/OpenSearch. O resto do sistema não muda.
- **Re-indexação automática:** disparar `indexer.run_index` via evento (ex: upload
  no S3 → Lambda).
- **Re-ranking:** inserir um cross-encoder entre a busca FAISS e a montagem do
  prompt para reordenar os candidatos.
- **Cache de respostas:** memoizar `(pergunta normalizada, top_k)` em Redis.
- **Streaming:** trocar `messages.create` por streaming para exibir a resposta
  token a token no frontend.

Ver também: [RUNBOOK.md](RUNBOOK.md) para procedimentos operacionais e o README
principal para a seção "Caminho para produção".
