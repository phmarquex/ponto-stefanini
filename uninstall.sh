#!/usr/bin/env bash
# Remove o Ponto instalado por install.sh. Use --purge para apagar também sessão/.env.
set -euo pipefail
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APP="$DATA/ponto"

rm -f "$HOME/.local/bin/ponto-gui" "$DATA/applications/ponto.desktop" "$DATA/icons/hicolor/scalable/apps/ponto.svg"
if [ "${1:-}" = "--purge" ]; then
  rm -rf "$APP"
else
  rm -rf "$APP/.venv" "$APP/ponto.py" "$APP/gui.py" "$APP/requirements.txt" "$APP/__pycache__"
  echo "Mantidos .env e profile/ em $APP (use --purge para apagar)."
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" || true
echo "Removido."
