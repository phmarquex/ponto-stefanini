#!/usr/bin/env bash
# Instala o Ponto para o usuário atual (sem sudo): app em ~/.local/share/ponto,
# lançador em ~/.local/bin/ponto-gui e atalho .desktop no menu de aplicativos.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="${XDG_DATA_HOME:-$HOME/.local/share}/ponto"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

command -v python3 >/dev/null || { echo "python3 não encontrado." >&2; exit 1; }
python3 -c "import tkinter" 2>/dev/null || {
  echo "tkinter não encontrado. Instale (ex.: sudo pacman -S tk | sudo apt install python3-tk | sudo dnf install python3-tkinter)." >&2
  exit 1
}

echo "==> Copiando arquivos para $APP"
mkdir -p "$APP" "$BIN" "$APPS" "$ICONS"
install -m 644 "$SRC/ponto.py" "$SRC/gui.py" "$SRC/requirements.txt" "$APP/"
install -m 644 "$SRC/packaging/ponto.svg" "$ICONS/ponto.svg"

echo "==> Criando ambiente virtual e instalando dependências"
[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
"$APP/.venv/bin/playwright" install chromium

if [ ! -f "$APP/.env" ]; then
  if [ -f "$SRC/.env" ]; then
    install -m 600 "$SRC/.env" "$APP/.env"
  else
    read -rp "Usuário (e-mail corporativo) [Enter para informar depois na interface]: " user || user=""
    printf 'PONTO_USER=%s\n' "$user" > "$APP/.env"
    chmod 600 "$APP/.env"
  fi
fi

echo "==> Criando lançador e atalho"
cat > "$BIN/ponto-gui" <<LAUNCH
#!/usr/bin/env bash
exec "$APP/.venv/bin/python" "$APP/gui.py" "\$@"
LAUNCH
chmod 755 "$BIN/ponto-gui"

cat > "$APPS/ponto.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Ponto
Comment=Marcação de ponto no Portal Horas
Exec=$BIN/ponto-gui
Icon=ponto
Terminal=false
Categories=Utility;
StartupWMClass=tk
DESK
chmod 644 "$APPS/ponto.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "${ICONS%/scalable/apps}/.." 2>/dev/null || true

echo "Pronto! Abra \"Ponto\" no menu de aplicativos ou rode: ponto-gui"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Obs.: $BIN não está no PATH." ;; esac
