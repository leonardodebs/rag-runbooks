"""Configuração compartilhada de testes.

Garante que o diretório `src/` esteja no sys.path para que os módulos possam ser
importados tanto como `import indexer` quanto via fixtures.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for caminho in (str(ROOT), str(SRC)):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)
