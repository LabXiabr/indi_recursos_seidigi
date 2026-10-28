#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then PYTHON="$(command -v python3)"; fi
args=()

# Busca a saida do design system oficial no clone local da Vidraria.
if [ -n "${VIDRARIA_CSS:-}" ]; then
  args+=(--brand-css "$VIDRARIA_CSS")
else
  for source in \
    "$HOME/git/LabXiabr/vidraria/design-system/generated/brand.css" \
    "$HOME/git/LabXiabr/vidraria/generated/brand.css" \
    "$HOME/git/LabXiabr/vidraria/vendor/vidraria/generated/brand.css"; do
    if [ -f "$source" ]; then args+=(--brand-css "$source"); break; fi
  done
fi
if [ -n "${VIDRARIA_LOGO:-}" ]; then args+=(--logo-svg "$VIDRARIA_LOGO"); fi

# Em erro, 'atualizar.py' retorna 1 e o HTML anterior permanece intocado.
"$PYTHON" "$ROOT/scripts/atualizar.py" "${args[@]}" "$@"

# Publicacao automatica opcional (a partir do Bequer): GIT_PUBLISH=1.
if [ "${GIT_PUBLISH:-0}" = 1 ]; then
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo 'ERRO: GIT_PUBLISH=1, mas nao existe checkout Git.' >&2
    exit 1
  fi
  if [ "$(git branch --show-current)" != main ]; then
    echo 'ERRO: publicacao exige branch main; HTML local ja foi atualizado.' >&2
    exit 1
  fi
  git add -- public/index.html
  if ! git diff --cached --quiet; then
    git commit -m "data: atualiza indicadores SEIDIGI $(date +%Y-%m-%d)"
    git push origin main
  fi
fi
