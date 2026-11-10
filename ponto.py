#!/usr/bin/env python3
"""Automação do Portal Horas (Stefanini) com login Microsoft + MFA.

Uso:
  ponto.py login      # só garante sessão válida (e tira screenshot do portal)
  ponto.py bater      # garante sessão e bate o ponto (após mapear o botão)

Sessão: perfil persistente em ./profile (cookies). Se a sessão ainda vale,
cai direto no portal; se pedir senha, preenche; se pedir aprovação no
Authenticator, mostra o número a digitar no app (stdout, MFA_NUMBER.txt e
notify-send, se existir).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
URL = "https://portalhoras.stefanini.com/"
PROFILE = BASE / "profile"
MFA_FILE = BASE / "MFA_NUMBER.txt"
TIMEOUT_TOTAL = 300  # segundos esperando login/MFA


def load_env():
    env = {}
    for line in (BASE / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def notify(msg):
    print(msg, flush=True)
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "critical", "Ponto", msg], check=False)


def fail(msg):
    """Notifica o erro na área de trabalho e encerra com código != 0."""
    notify(msg)
    raise SystemExit(1)


def visible(pg, sel):
    try:
        return pg.locator(sel).filter(visible=True).count() > 0
    except Exception:
        return False


def in_portal(pg):
    # Portal logado: host do portal, fora da tela de login e sem o erro de sessão.
    if "portalhoras.stefanini.com" not in pg.url:
        return False
    path = pg.url.split("portalhoras.stefanini.com", 1)[1].split("?")[0].split("#")[0]
    if path in ("", "/"):
        return False
    if visible(pg, "input[value='Entrar no portal']") or visible(pg, "input[name='username']"):
        return False
    return pg.locator(".x-viewport, .x-body").count() > 0 and not visible(pg, "text=Sua sessão expirou")


def ensure_login(pg, env):
    pg.goto(URL, wait_until="domcontentloaded")
    start = time.time()
    last_mfa = None
    email_attempts = 0
    while time.time() - start < TIMEOUT_TOTAL:
        pg.wait_for_timeout(1500)
        url = pg.url
        try:
            pg.screenshot(path=str(BASE / "debug.png"))
        except Exception:
            pass

        if "login.microsoftonline.com" in url or "microsoftonline" in url:
            NUM = "#idRemoteNGC_DisplaySign, #idRichContext_DisplaySign"
            if visible(pg, NUM):  # number matching (login sem senha ou pós-senha)
                n = pg.locator(NUM).filter(visible=True).first.inner_text().strip()
                if n != last_mfa:
                    last_mfa = n
                    MFA_FILE.write_text(n)
                    notify(f"MFA: digite o número {n} no Microsoft Authenticator")
                continue
            if visible(pg, "#idDiv_SAOTCAS_Title, #idDiv_SAOTCC_Description"):
                notify("MFA: aprove a notificação / informe o código no app")
                continue
            if visible(pg, "#i0116"):
                if email_attempts >= 2:
                    fail("Tela de e-mail repetida; veja debug.png. Abortando.")
                email_attempts += 1
                pg.fill("#i0116", env["PONTO_USER"])
                pg.click("#idSIButton9")
                pg.wait_for_timeout(3000)
                continue
            if visible(pg, "#i0118"):
                # Por segurança a senha NUNCA é enviada automaticamente (evita bloqueio de conta).
                fail("Microsoft pediu senha em vez do Authenticator; veja debug.png. Nada foi enviado.")
            if visible(pg, "#KmsiCheckboxField, #idBtn_Back"):  # Continuar conectado?
                if visible(pg, "#KmsiCheckboxField"):
                    pg.check("#KmsiCheckboxField")
                pg.click("#idSIButton9")
                continue
            if visible(pg, "[data-test-id], .table-row"):  # escolher conta
                row = pg.locator(f"[data-test-id='{env['PONTO_USER']}']")
                if row.count():
                    row.first.click()
                continue
            continue

        # Páginas do próprio portal
        if visible(pg, "text=Confirmar preferências"):
            pg.get_by_text("Confirmar preferências").click()
            continue
        if visible(pg, "input[value='Entrar no portal']"):
            pg.locator("input[value='Entrar no portal']:visible").first.click()
            continue
        if visible(pg, "text=Sua sessão expirou"):
            pg.goto(URL, wait_until="domcontentloaded")
            continue
        if in_portal(pg):
            return
    fail("Timeout aguardando login/MFA.")


LAST_FILE = BASE / "last_punch.txt"
MIN_INTERVAL = 30 * 60  # segundos; evita marcação duplicada


def recent_punch():
    try:
        return time.time() - float(LAST_FILE.read_text()) < MIN_INTERVAL
    except Exception:
        return False


def bater(pg, force=False):
    """Abre o Relógio de Ponto Virtual e clica em Efetuar Marcação."""
    if recent_punch() and not force:
        fail("Já houve marcação há menos de 30 min. Use --force para marcar mesmo assim.")
    pg.mouse.click(475, 510)  # card "Registre aqui" no Mural
    btn = pg.get_by_text("Efetuar Marcação")
    try:
        btn.first.wait_for(state="visible", timeout=15000)
    except Exception:
        pg.screenshot(path=str(BASE / "erro_bater.png"))
        fail("Tela do relógio não abriu; veja erro_bater.png. Nada foi marcado.")
    hora = pg.locator("text=/^\\d{1,2}:\\d{2}:\\d{2}$/").first.inner_text()
    btn.first.click()
    pg.wait_for_timeout(4000)
    pg.screenshot(path=str(BASE / "resultado_ponto.png"))
    if not pg.get_by_text("MARCACAO EFETUADA").count():
        fail("Sem confirmação 'MARCACAO EFETUADA'; veja resultado_ponto.png e confira no portal.")
    LAST_FILE.write_text(str(time.time()))
    print(f"MARCAÇÃO EFETUADA às {hora} (horário do servidor).")
    notify(f"MARCAÇÃO EFETUADA às {hora} (horário do servidor).")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    headless = os.environ.get("HEADED") != "1"
    env = load_env()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=headless, viewport={"width": 1366, "height": 900}
        )
        # Sem WebAuthn a Microsoft não força passkey/FIDO (que trava no headless).
        ctx.add_init_script(
            "Object.defineProperty(window,'PublicKeyCredential',{value:undefined,configurable:true});"
        )
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            ensure_login(pg, env)
            pg.wait_for_timeout(3000)
            print("Login OK:", pg.url)
            pg.screenshot(path=str(BASE / "portal.png"))
            if cmd == "bater":
                bater(pg, force="--force" in sys.argv)
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
