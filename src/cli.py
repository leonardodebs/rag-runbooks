"""Interface de linha de comando do sistema RAG.

Permite fazer uma pergunta direta, rodar em modo interativo (várias perguntas em
loop) e ajustar o top_k. A saída usa Rich para destacar a resposta e listar as
fontes consultadas com seus scores de relevância.

Exemplos:
    python src/cli.py "Como faço rollback de um serviço ECS?"
    python src/cli.py --interactive
    python src/cli.py --top-k 5 "Quais são os passos para investigar um spike de custo?"
"""
from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

try:
    from . import config
    from .rag import RAGEngine
except ImportError:  # pragma: no cover
    import config
    from rag import RAGEngine

console = Console()


def render_resposta(resultado: dict) -> None:
    """Imprime a resposta formatada e a tabela de fontes consultadas."""
    console.print()
    console.print(Panel(Markdown(resultado["answer"]), title="[bold green]Resposta",
                        border_style="green"))

    if resultado["sources"]:
        tabela = Table(title="Fontes consultadas", show_header=True, header_style="bold cyan")
        tabela.add_column("Runbook", style="yellow")
        tabela.add_column("Relevância", justify="right", style="magenta")
        for fonte in resultado["sources"]:
            tabela.add_row(fonte["file"], f"{fonte['score']:.4f}")
        console.print(tabela)
    else:
        console.print("[dim]Nenhuma fonte relevante encontrada.[/dim]")

    # Rodapé com telemetria de uso.
    console.print(
        f"[dim]Tokens: {resultado['tokens_used']} | "
        f"Custo estimado: US$ {resultado['cost_usd']:.6f}[/dim]"
    )
    console.print()


def perguntar(engine: RAGEngine, pergunta: str, top_k: int) -> None:
    """Faz uma pergunta ao engine e renderiza o resultado, tratando erros."""
    try:
        with console.status("[bold blue]Buscando nos runbooks e consultando a Claude..."):
            resultado = engine.retrieve_and_generate(pergunta, top_k=top_k)
        render_resposta(resultado)
    except Exception as exc:  # noqa: BLE001 - queremos mostrar qualquer erro ao usuário
        console.print(f"[bold red]Erro:[/bold red] {exc}")


def modo_interativo(engine: RAGEngine, top_k: int) -> None:
    """Loop de perguntas: lê do usuário até 'sair', 'exit' ou Ctrl+D."""
    console.print(Panel(
        "Modo interativo. Digite sua pergunta e pressione Enter.\n"
        "Comandos: 'sair' ou 'exit' para encerrar.",
        title="[bold]RAG Runbooks", border_style="blue",
    ))
    while True:
        try:
            pergunta = console.input("[bold cyan]Pergunta>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Encerrando.[/dim]")
            break
        if not pergunta:
            continue
        if pergunta.lower() in {"sair", "exit", "quit"}:
            console.print("[dim]Encerrando.[/dim]")
            break
        perguntar(engine, pergunta, top_k)


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do CLI."""
    parser = argparse.ArgumentParser(
        description="Pergunte aos runbooks de infraestrutura via RAG + Claude.",
    )
    parser.add_argument("pergunta", nargs="?", help="A pergunta a ser respondida.")
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Modo interativo: faz várias perguntas em loop.",
    )
    parser.add_argument(
        "--top-k", type=int, default=config.DEFAULT_TOP_K,
        help=f"Quantos chunks recuperar (padrão: {config.DEFAULT_TOP_K}).",
    )
    args = parser.parse_args(argv)

    if not args.interactive and not args.pergunta:
        parser.error("informe uma pergunta ou use --interactive")

    # Inicializa o engine uma única vez (carrega índice e modelo).
    try:
        with console.status("[bold blue]Carregando índice e modelo..."):
            engine = RAGEngine()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Falha ao inicializar:[/bold red] {exc}")
        return 1

    if args.interactive:
        modo_interativo(engine, args.top_k)
    else:
        perguntar(engine, args.pergunta, args.top_k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
