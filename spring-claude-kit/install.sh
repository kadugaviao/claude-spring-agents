#!/usr/bin/env bash
# Instala a skill spring-boot, os subagentes e os hooks em ~/.claude (valem para todos os projetos).
# Arquivos que já existirem com conteúdo diferente ganham backup em <arquivo>.<AAAAMMDD-HHMMSS>.bak
# antes de serem trocados. Backups anteriores nunca são sobrescritos.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

# Os hooks e os prompts dos agentes apontam para $HOME/.claude fixo.
if [[ "$DEST" != "$HOME/.claude" ]]; then
  echo "Erro: CLAUDE_CONFIG_DIR=$DEST, mas os agentes chamam \$HOME/.claude/hooks." >&2
  echo "Troque \$HOME/.claude nos arquivos de claude/agents/ antes de instalar." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erro: python3 não encontrado. Os hooks precisam dele." >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"

copy() {
  local from="$1" to="$2" bak
  mkdir -p "$(dirname "$to")"
  if [[ -f "$to" ]] && ! cmp -s "$from" "$to"; then
    bak="$to.$STAMP.bak"
    if [[ -e "$bak" ]]; then
      echo "Erro: $bak já existe; rode de novo daqui a um segundo." >&2
      exit 1
    fi
    cp -p "$to" "$bak"
    echo "  backup: $bak"
  fi
  cp "$from" "$to"
  echo "  ok: $to"
}

echo "Instalando em $DEST"
while IFS= read -r -d '' file; do
  copy "$file" "$DEST/${file#"$SRC"/}"
done < <(find "$SRC" -type f -print0)

chmod +x "$DEST/hooks/guard-paths.py" "$DEST/hooks/bash-allowlist.py"

echo
echo "Pronto. Abra (ou reinicie) o Claude Code num projeto Spring e rode /agents para conferir."
