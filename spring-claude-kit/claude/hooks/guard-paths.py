#!/usr/bin/env python3
"""
Hook PreToolUse para Edit/Write: restringe onde um subagente pode escrever.

Uso (no frontmatter do agente):
    python3 "$HOME/.claude/hooks/guard-paths.py" tests-only
    python3 "$HOME/.claude/hooks/guard-paths.py" no-applied-migrations

Modos:
    tests-only             só permite arquivos dentro de src/test (e variações como src/it)
                           do projeto atual ($CLAUDE_PROJECT_DIR, ou o cwd se ela não existir).
    no-applied-migrations  só permite arquivos dentro do projeto e bloqueia edição de migrations
                           versionadas (V<n>__*.sql/.java) que já aparecem no histórico do git.

Sem file_path na entrada, a edição é bloqueada (falha fechada).
Saída: exit 0 libera; exit 2 bloqueia, e a mensagem no stderr volta para o Claude.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import NoReturn
from pathlib import Path

TEST_DIRS = re.compile(r"/src/(test|it|integrationTest|intTest|testFixtures)/")
VERSIONED_MIGRATION = re.compile(r"^V\d+([._]\d+)*__.+\.(sql|java)$")


def block(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(2)


def target_path(data: dict) -> Path | None:
    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(data.get("cwd") or os.getcwd()) / path
    return path.resolve()


def project_root(data: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()).resolve()


def is_committed(path: Path) -> bool:
    if not path.parent.is_dir():
        return False  # pasta nova: a migration não pode estar no histórico
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", f":(literal){path.name}"],
            cwd=path.parent, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True  # na dúvida, trata como aplicada (falha fechada)
    # fora de um repositório git (código 128) não há como saber: libera
    return result.returncode == 0 and bool(result.stdout.strip())


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"tests-only", "no-applied-migrations"}:
        block("guard-paths.py: modo inválido. Use 'tests-only' ou 'no-applied-migrations'.")
    mode = sys.argv[1]

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        block("guard-paths.py: entrada do hook inválida; edição bloqueada por segurança.")

    path = target_path(data)
    if path is None:
        block("guard-paths.py: a entrada não tem file_path; edição bloqueada por segurança.")

    root = project_root(data)
    try:
        relative = "/" + path.relative_to(root).as_posix()
    except ValueError:
        relative = None

    if mode == "no-applied-migrations" and relative is None:
        block(f"Bloqueado: este agente só pode editar arquivos dentro do projeto ({root}). Tentou editar: {path}.")

    if mode == "tests-only":
        if relative is None or not TEST_DIRS.search(relative):
            block(
                f"Bloqueado: este agente só pode editar arquivos de teste (src/test/...) "
                f"dentro de {root}. Tentou editar: {path}. Se o código de produção precisa mudar, "
                f"reporte isso na resposta final em vez de editar."
            )

    if mode == "no-applied-migrations" and VERSIONED_MIGRATION.match(path.name) and is_committed(path):
        block(
            f"Bloqueado: {path.name} já foi commitada e pode ter rodado em algum banco "
            f"(o checksum do Flyway quebraria). Crie uma nova migration com a correção."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
