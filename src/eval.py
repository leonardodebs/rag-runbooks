"""Avaliação automática do sistema RAG.

Define um conjunto de perguntas de teste, cada uma com:
  - palavras-chave esperadas na resposta
  - o runbook que deveria ser a fonte correta

Roda todas pelo RAG e verifica:
  - se as palavras-chave aparecem na resposta (qualidade da geração)
  - se o runbook correto apareceu entre as fontes recuperadas (precision@k)

Uso: python src/eval.py
"""
from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

try:
    from . import config
    from .rag import RAGEngine
except ImportError:  # pragma: no cover
    import config
    from rag import RAGEngine

console = Console()

# 10 perguntas de teste. `keywords`: termos que esperamos na resposta.
# `expected_source`: runbook que deveria ser recuperado como fonte.
TEST_CASES: list[dict] = [
    {
        "question": "Como faço rollback de um serviço ECS?",
        "keywords": ["task definition", "revisão"],
        "expected_source": "ecs-deployment.md",
    },
    {
        "question": "Como resolver erro 502 no ALB?",
        "keywords": ["502", "timeout"],
        "expected_source": "alb-502-errors.md",
    },
    {
        "question": "Quais os passos para investigar um spike de custo na AWS?",
        "keywords": ["cost explorer", "custo"],
        "expected_source": "cost-spike.md",
    },
    {
        "question": "Como executar um failover manual no RDS Multi-AZ?",
        "keywords": ["failover", "standby"],
        "expected_source": "rds-failover.md",
    },
    {
        "question": "O que fazer quando uma instância EC2 está com CPU alta?",
        "keywords": ["cpu", "cloudwatch"],
        "expected_source": "ec2-troubleshooting.md",
    },
    {
        "question": "Como conter uma credencial IAM comprometida?",
        "keywords": ["chave", "cloudtrail"],
        "expected_source": "security-incident.md",
    },
    {
        "question": "Por que não consigo conectar na minha instância dentro da VPC?",
        "keywords": ["security group", "rota"],
        "expected_source": "vpc-connectivity.md",
    },
    {
        "question": "Qual o fluxo de triagem ao receber um alerta de plantão?",
        "keywords": ["severidade", "escalar"],
        "expected_source": "on-call-checklist.md",
    },
    {
        "question": "Como restaurar um banco RDS para um ponto no tempo?",
        "keywords": ["point-in-time", "restore"],
        "expected_source": "rds-failover.md",
    },
    {
        "question": "Como diferenciar um erro 503 de um 502 no load balancer?",
        "keywords": ["503", "saudáveis"],
        "expected_source": "alb-502-errors.md",
    },
]


def keywords_presentes(resposta: str, keywords: list[str]) -> list[bool]:
    """Retorna, para cada palavra-chave, se ela aparece na resposta (case-insensitive)."""
    texto = resposta.lower()
    return [kw.lower() in texto for kw in keywords]


def fonte_correta(sources: list[dict], esperada: str) -> bool:
    """Indica se o runbook esperado está entre as fontes recuperadas."""
    return any(s["file"] == esperada for s in sources)


def run_eval(top_k: int = config.DEFAULT_TOP_K) -> dict:
    """Roda todos os casos de teste e retorna as métricas agregadas."""
    engine = RAGEngine()

    tabela = Table(title="Avaliação RAG", show_header=True, header_style="bold cyan")
    tabela.add_column("#", justify="right")
    tabela.add_column("Pergunta", style="white", max_width=40)
    tabela.add_column("Fonte correta?", justify="center")
    tabela.add_column("Keywords", justify="center")

    total = len(TEST_CASES)
    acertos_fonte = 0
    keywords_ok = 0
    keywords_total = 0
    custo_total = 0.0
    tokens_total = 0

    for i, caso in enumerate(TEST_CASES, start=1):
        resultado = engine.retrieve_and_generate(caso["question"], top_k=top_k)

        fonte_ok = fonte_correta(resultado["sources"], caso["expected_source"])
        acertos_fonte += int(fonte_ok)

        presencas = keywords_presentes(resultado["answer"], caso["keywords"])
        keywords_ok += sum(presencas)
        keywords_total += len(presencas)

        custo_total += resultado["cost_usd"]
        tokens_total += resultado["tokens_used"]

        marca_fonte = "[green]✓[/green]" if fonte_ok else "[red]✗[/red]"
        marca_kw = f"{sum(presencas)}/{len(presencas)}"
        tabela.add_row(str(i), caso["question"], marca_fonte, marca_kw)

    precision_at_k = acertos_fonte / total
    recall_keywords = keywords_ok / keywords_total if keywords_total else 0.0

    console.print(tabela)
    console.print()
    console.print(f"[bold]Precision@{top_k} (fonte correta recuperada):[/bold] "
                  f"{precision_at_k:.0%} ({acertos_fonte}/{total})")
    console.print(f"[bold]Cobertura de keywords na resposta:[/bold] "
                  f"{recall_keywords:.0%} ({keywords_ok}/{keywords_total})")
    console.print(f"[bold]Tokens totais:[/bold] {tokens_total}")
    console.print(f"[bold]Custo total estimado:[/bold] US$ {custo_total:.6f}")

    return {
        "total": total,
        "precision_at_k": precision_at_k,
        "keyword_coverage": recall_keywords,
        "tokens_total": tokens_total,
        "cost_total_usd": round(custo_total, 6),
    }


def main() -> int:
    try:
        run_eval()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Erro na avaliação:[/bold red] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
