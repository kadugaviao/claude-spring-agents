#!/usr/bin/env python3
r"""
Hook PreToolUse para Bash: só libera comandos cujo início casa com um regex.

Uso (no frontmatter do agente):
    python3 "$HOME/.claude/hooks/bash-allowlist.py" '^git (diff|log|show|status)\b'

Regras:
- O comando é dividido com shlex, respeitando aspas. O regex é testado contra o
  primeiro comando já normalizado (shlex.join).
- grep e find são sempre liberados, como primeiro comando ou depois de um pipe. No Linux, macOS e WSL
  o Claude Code tira Glob e Grep de quem tem Bash e busca com find/grep pelo Bash.
  No find, ações que executam, apagam ou gravam arquivo (-exec, -delete, -fprint...) bloqueiam.
- Pipes só para leitura (grep, egrep, find, head, tail, wc, cut). xargs não.
- Maven: bloqueia exec:, antrun: e -Dexec.*. Gradle: bloqueia -I, --init-script e -Dorg.gradle.jvmargs.
- Antes do shlex, cada caractere é conferido (o shell expande coisas que o shlex não vê):
  fora de aspas, só letras, números, espaço e _ . / : = , @ % + - * ? ~ |, mais \( e \) no find
  e o '2>&1' como palavra isolada. Tudo o mais bloqueia ($ { } ( ) [ ] ! ; & < > ` # \ e quebra de linha).
  Dentro de '...' vale tudo. Dentro de "..." bloqueia $ e `. $'...' e $"..." bloqueiam.
- Antes do comando, só as variáveis MAVEN_OPTS, GRADLE_OPTS e JAVA_HOME (ex.: MAVEN_OPTS=-Xmx2g ./mvnw).
  Elas são removidas antes do teste do regex. Qualquer outra atribuição (PATH, LD_PRELOAD...) bloqueia.
- Em comandos git, '--no-pager' entre as opções globais é removido antes do teste do regex.
  O caminho de '-C' com espaço chega ao regex entre aspas simples (shlex.join), ex.: git -C '/a b' diff.

Saída: exit 0 libera; exit 2 bloqueia, e a mensagem no stderr volta para o Claude.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from typing import NoReturn

SEARCH = {"grep", "find"}
SAFE_PIPES = {"grep", "egrep", "find", "head", "tail", "wc", "cut"}
# -rm é sinônimo de -delete no bfs, o find embutido do Claude Code.
FIND_FORBIDDEN = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-rm", "-fprint", "-fprint0", "-fprintf", "-fls"}
# Opções do find cujo próximo token é valor, não ação (find . -name "-exec" é inofensivo).
FIND_TAKES_VALUE = {"-name", "-iname", "-path", "-ipath", "-wholename", "-regex", "-iregex", "-lname",
                    "-newer", "-type", "-user", "-group", "-perm", "-size", "-mtime", "-mmin", "-maxdepth", "-mindepth"}
# Argumentos que fazem Maven/Gradle rodar comando ou script arbitrário.
MAVEN_EXEC = re.compile(r"^(exec:|antrun:|-Dexec\.)|exec-maven-plugin|maven-antrun-plugin")
GRADLE_EXEC = re.compile(r"^(-I|--init-script|-Dorg\.gradle\.jvmargs)")
SAFE_UNQUOTED = set(" _./:=,@%+-*?~|")
FIND_SEGMENT = re.compile(r"^\s*find\s")
STDERR_TO_STDOUT = re.compile(r"(?<![^\s|])2>&1(?![^\s|])")
# ( e ) só chegam aqui vindos de \( \) no find ou de aspas (check_chars barra o resto).
OPERATOR = re.compile(r"^[;<>|&]+$")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
ALLOWED_ENV = re.compile(r"^(MAVEN_OPTS|GRADLE_OPTS|JAVA_HOME)=")


def block(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(2)


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # '#' entre aspas é comum em -Dtest='Classe#metodo'
    return list(lexer)


def check_chars(command: str) -> None:
    """Lista de caracteres permitidos, respeitando aspas, antes de qualquer interpretação."""
    quote, segment, i = "", "", 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            quote = "" if c == "'" else quote
        elif quote == '"':
            if c == '"':
                quote = ""
            elif c in "$`":
                block(f"Bloqueado: $ e ` dentro de aspas duplas são expandidos pelo shell; use aspas simples. Recebido: {command!r}")
            elif c == "\\":
                segment += c
                i += 1  # \" e \\ dentro de "..." são literais
        elif c == "$" and command[i + 1:i + 2] in ("'", '"'):
            block(f"Bloqueado: $'...' e $\"...\" não são permitidos. Recebido: {command!r}")
        elif c in "'\"":
            quote = c
        elif c == "\\" and command[i + 1:i + 2] in ("(", ")") and FIND_SEGMENT.match(segment):
            segment += c
            i += 1
        elif c == "|":
            segment = ""
            i += 1
            continue
        elif not (c.isalnum() or c in SAFE_UNQUOTED):
            block(
                f"Bloqueado: caractere {c!r} fora de aspas. Fora de aspas só valem letras, números, espaço "
                f"e _ . / : = , @ % + - * ? ~ | (e \\( \\) no find). Use aspas simples. Recebido: {command!r}"
            )
        segment += command[i:i + 1]
        i += 1
    if quote:
        block(f"Bloqueado: aspas sem fechar. Recebido: {command!r}")


def strip_no_pager(words: list[str]) -> list[str]:
    """Remove --no-pager entre as opções globais do git (antes do subcomando)."""
    words, i = list(words), 1
    while i < len(words) and words[i] in ("--no-pager", "-C"):
        if words[i] == "--no-pager":
            del words[i]
        else:
            i += 2
    return words


def has_find_action(words: list[str]) -> bool:
    skip = False
    for word in words[1:]:
        if skip:
            skip = False
        elif word in FIND_TAKES_VALUE:
            skip = True
        elif word in FIND_FORBIDDEN:
            return True
    return False


def main() -> None:
    if len(sys.argv) != 2:
        block("bash-allowlist.py: passe o regex de comandos permitidos como argumento.")
    try:
        allowed = re.compile(sys.argv[1])
    except re.error as e:
        block(f"bash-allowlist.py: regex inválido ({e}).")

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        block("bash-allowlist.py: entrada do hook inválida; comando bloqueado por segurança.")

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = (data.get("tool_input") or {}).get("command", "").strip()

    command = STDERR_TO_STDOUT.sub(" ", command)
    check_chars(command)

    try:
        tokens = tokenize(command)
    except ValueError as e:
        block(f"Bloqueado: não consegui interpretar o comando ({e}). Recebido: {command!r}")

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token == "|":
            segments.append([])
        elif OPERATOR.match(token):
            block(
                "Bloqueado: este agente não pode encadear comandos nem redirecionar saída "
                f"(; && || & > < ( )). Rode um comando por vez. Recebido: {command!r}"
            )
        else:
            segments[-1].append(token)

    if any(not segment for segment in segments):
        block(f"Bloqueado: pipe vazio ou comando vazio. Recebido: {command!r}")

    first, *pipes = segments
    while ASSIGNMENT.match(first[0]):
        if not ALLOWED_ENV.match(first[0]):
            block(
                f"Bloqueado: só MAVEN_OPTS, GRADLE_OPTS e JAVA_HOME podem vir antes do comando. "
                f"Recebido: {first[0].split('=', 1)[0]!r}"
            )
        first = first[1:]
        if not first:
            block(f"Bloqueado: só atribuição de variável, sem comando. Recebido: {command!r}")
    if first[0] == "git":
        first = strip_no_pager(first)
    if first[0] not in SEARCH and not allowed.match(shlex.join(first)):
        block(f"Bloqueado: este agente só pode rodar find, grep e comandos que casam com {allowed.pattern!r}. Recebido: {command!r}")
    for segment in pipes:
        if segment[0] not in SAFE_PIPES:
            block(f"Bloqueado: pipe só é permitido para {'/'.join(sorted(SAFE_PIPES))}. Recebido: {shlex.join(segment)!r}")
    for segment in [first, *pipes]:
        if segment[0] == "find" and has_find_action(segment):
            block(f"Bloqueado: find só para busca; {'/'.join(sorted(FIND_FORBIDDEN))} não são permitidos. Recebido: {command!r}")
    tool = first[0].rsplit("/", 1)[-1]
    args = first[1:]
    # "-D exec.x=1" (com espaço) vira "-Dexec.x=1" para o teste.
    joined = [a + b if a == "-D" else a for a, b in zip(args, args[1:] + [""])]
    if tool in ("mvn", "mvnw") and any(MAVEN_EXEC.search(a) for a in joined):
        block(f"Bloqueado: exec:, antrun: e -Dexec.* rodam comandos arbitrários. Recebido: {command!r}")
    if tool in ("gradle", "gradlew") and any(GRADLE_EXEC.match(a) for a in joined):
        block(f"Bloqueado: -I, --init-script e -Dorg.gradle.jvmargs rodam código arbitrário. Recebido: {command!r}")

    sys.exit(0)


if __name__ == "__main__":
    main()
