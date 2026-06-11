// Frontend do RAG Runbooks — conversa com a API FastAPI (mesmo host).

// Elementos da página.
const form = document.getElementById("composer");
const questionInput = document.getElementById("question");
const topKSelect = document.getElementById("top-k");
const sendBtn = document.getElementById("send-btn");

const resultEl = document.getElementById("result");
const answerBody = document.getElementById("answer-body");
const answerMeta = document.getElementById("answer-meta");
const sourcesEl = document.getElementById("sources");
const loadingEl = document.getElementById("loading");
const errorBox = document.getElementById("error-box");
const suggestions = document.getElementById("suggestions");

const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const statusMeta = document.getElementById("status-meta");
const runbookList = document.getElementById("runbook-list");
const modelTag = document.getElementById("model-tag");

// Escapa HTML para evitar injeção ao renderizar a resposta.
function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

// Renderização mínima de markdown: `código inline` e **negrito**.
function renderAnswer(texto) {
  let html = escapeHtml(texto);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html;
}

// Mostra apenas uma das seções (resultado / loading / erro) por vez.
function setView(view) {
  resultEl.hidden = view !== "result";
  loadingEl.hidden = view !== "loading";
  if (view !== "error") errorBox.hidden = true;
}

function showError(mensagem) {
  errorBox.textContent = mensagem;
  errorBox.hidden = false;
  setView("error");
}

// Carrega o status do índice (/health) e a lista de runbooks (/runbooks).
async function carregarStatus() {
  try {
    const [health, runbooks] = await Promise.all([
      fetch("/health").then((r) => r.json()),
      fetch("/runbooks").then((r) => r.json()),
    ]);

    statusDot.classList.add("ok");
    statusText.textContent = "Índice carregado";
    const data = health.index_built_at
      ? new Date(health.index_built_at).toLocaleString("pt-BR")
      : "—";
    statusMeta.textContent =
      `${health.runbooks_indexed} runbooks · ${health.chunks_indexed} chunks\n` +
      `Indexado em ${data}`;
    modelTag.textContent = health.model || "";

    runbookList.innerHTML = "";
    runbooks.runbooks.forEach((rb) => {
      const li = document.createElement("li");
      li.dataset.file = rb.file;
      li.innerHTML =
        `<span class="rb-name">${escapeHtml(rb.file)}</span>` +
        `<span class="rb-chunks">${rb.chunks}</span>`;
      runbookList.appendChild(li);
    });
  } catch (e) {
    statusDot.classList.add("bad");
    statusText.textContent = "Índice indisponível";
    statusMeta.textContent = "Rode `make index` para gerar o índice.";
    runbookList.innerHTML = '<li class="muted">—</li>';
  }
}

// Destaca na sidebar os runbooks usados como fonte da última resposta.
function destacarFontes(arquivos) {
  document.querySelectorAll(".runbook-list li").forEach((li) => {
    li.classList.toggle("active", arquivos.includes(li.dataset.file));
  });
}

// Envia a pergunta para /query e renderiza a resposta.
async function perguntar(pergunta) {
  const topK = parseInt(topKSelect.value, 10);
  setView("loading");
  sendBtn.disabled = true;

  try {
    const resp = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: pergunta, top_k: topK }),
    });

    if (!resp.ok) {
      const detalhe = await resp.json().catch(() => ({}));
      throw new Error(detalhe.detail || `Erro ${resp.status}`);
    }

    const data = await resp.json();
    answerBody.innerHTML = renderAnswer(data.answer);
    answerMeta.textContent =
      `${data.tokens} tokens · US$ ${data.cost_usd.toFixed(6)}`;

    // Monta os chips de fontes citadas.
    sourcesEl.innerHTML = '<span class="sources-label">Fontes</span>';
    if (data.sources.length === 0) {
      sourcesEl.innerHTML += '<span class="muted">nenhuma</span>';
    }
    data.sources.forEach((s) => {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.innerHTML =
        `📄 ${escapeHtml(s.file)} <span class="score">${s.score.toFixed(4)}</span>`;
      sourcesEl.appendChild(chip);
    });

    destacarFontes(data.sources.map((s) => s.file));
    setView("result");
  } catch (e) {
    showError("Erro: " + e.message);
  } finally {
    sendBtn.disabled = false;
  }
}

// Eventos.
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const pergunta = questionInput.value.trim();
  if (pergunta) perguntar(pergunta);
});

suggestions.addEventListener("click", (e) => {
  if (e.target.classList.contains("chip-suggestion")) {
    questionInput.value = e.target.textContent.trim();
    perguntar(questionInput.value);
  }
});

// Inicialização.
carregarStatus();
