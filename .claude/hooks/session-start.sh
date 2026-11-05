#!/bin/bash
# Installs the Ponytail and Superpowers plugins in Claude Code cloud sessions.
# Project settings enable them, but cloud sessions don't register third-party
# marketplaces on their own, so this hook does it.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# marketplace name|GitHub repo|plugin id
plugins=(
  "ponytail|DietrichGebert/ponytail|ponytail@ponytail"
  "superpowers-dev|obra/superpowers|superpowers@superpowers-dev"
)

marketplaces="$(claude plugin marketplace list 2>/dev/null || true)"
installed="$(claude plugin list 2>/dev/null || true)"

for entry in "${plugins[@]}"; do
  IFS='|' read -r market repo plugin <<<"$entry"
  if ! grep -qw -- "$market" <<<"$marketplaces"; then
    claude plugin marketplace add "$repo" >&2
  fi
  if ! grep -qF -- "$plugin" <<<"$installed"; then
    claude plugin install "$plugin" >&2
  fi
done
