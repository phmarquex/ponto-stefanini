# ponto

Automação de marcação de ponto no Portal Horas (Apdata) com login Microsoft
sem senha (Authenticator com number matching), via Playwright.

## Setup
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/playwright install chromium
    cp .env.example .env   # preencha PONTO_USER

## Uso
    .venv/bin/python ponto.py login   # garante sessão
    .venv/bin/python ponto.py bater   # bate o ponto (recusa se houve marcação < 30 min; --force ignora)

A sessão fica em `./profile`. Quando expira, o script mostra o número a digitar
no Microsoft Authenticator (terminal, `MFA_NUMBER.txt` e `notify-send`) e espera até 5 min.
A senha nunca é enviada automaticamente.

## Interface gráfica e instalação (Linux)
    ./install.sh      # instala em ~/.local/share/ponto + atalho "Ponto" no menu (.desktop)
    ponto-gui         # ou abra pelo menu de aplicativos
    ./uninstall.sh    # remove (--purge apaga também sessão e .env)

O instalador também registra o início automático com a sessão (`~/.config/autostart/ponto.desktop`, abre minimizado na bandeja). Fechar a janela mantém o app na bandeja; use "Sair" no menu do ícone para encerrar. Em GNOME é preciso a extensão AppIndicator para ver o ícone.

Requer `python3` com `tkinter`. A interface roda o `ponto.py`, mostra o log e destaca o número do Authenticator.

## Limitações
O card "Registre aqui" é clicado por coordenada (475, 510); se o layout mudar, o script falha sem marcar.
Use apenas na sua própria conta e conforme a política da empresa.
