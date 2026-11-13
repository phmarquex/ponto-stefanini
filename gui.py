#!/usr/bin/env python3
"""Interface gráfica (tkinter) para o ponto.py."""
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:  # bandeja do sistema é opcional
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    pystray = None

BASE = Path(__file__).resolve().parent
SCRIPT = BASE / "ponto.py"
ENV_FILE = BASE / ".env"
LAST_FILE = BASE / "last_punch.txt"
MFA_RE = re.compile(r"MFA: digite o número (\d+)")


def read_user():
    try:
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("PONTO_USER="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def write_user(user):
    ENV_FILE.write_text(f"PONTO_USER={user}\n")
    ENV_FILE.chmod(0o600)


def make_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill="#2563eb", outline="white", width=3)
    d.line((32, 32, 32, 14), fill="white", width=4)
    d.line((32, 32, 46, 38), fill="white", width=4)
    return img


class App(tk.Tk):
    def __init__(self, start_hidden=False):
        super().__init__()
        self.title("Ponto")
        self.geometry("560x520")
        self.minsize(480, 420)
        self.proc = None
        self.q = queue.Queue()

        pad = {"padx": 12, "pady": 6}
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Usuário:").pack(side="left")
        self.user = tk.StringVar(value=read_user())
        ttk.Entry(top, textvariable=self.user).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Salvar", command=self.save_user).pack(side="left")

        self.last = tk.StringVar()
        ttk.Label(self, textvariable=self.last).pack(anchor="w", **pad)

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        self.force = tk.BooleanVar()
        self.headed = tk.BooleanVar()
        ttk.Checkbutton(opts, text="Forçar (ignorar intervalo de 30 min)", variable=self.force).pack(anchor="w")
        ttk.Checkbutton(opts, text="Mostrar navegador", variable=self.headed).pack(anchor="w")

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.btn_bater = ttk.Button(btns, text="Bater ponto", command=lambda: self.run("bater"))
        self.btn_bater.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_login = ttk.Button(btns, text="Verificar sessão", command=lambda: self.run("login"))
        self.btn_login.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_cancel = ttk.Button(btns, text="Cancelar", command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=(4, 0))

        self.mfa = tk.StringVar()
        self.mfa_label = ttk.Label(self, textvariable=self.mfa, font=("TkDefaultFont", 22, "bold"),
                                   foreground="#b45309", anchor="center")
        self.mfa_label.pack(fill="x", padx=12)

        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.status).pack(anchor="w", **pad)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log = tk.Text(frame, height=10, state="disabled", wrap="word")
        sb = ttk.Scrollbar(frame, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.tray = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.setup_tray()
        if start_hidden and self.tray:
            self.withdraw()

        self.refresh_last()
        self.after(100, self.poll)
        if not self.user.get():
            self.status.set("Informe seu usuário (e-mail) e clique em Salvar.")

    # --- bandeja
    def setup_tray(self):
        """Bandeja em subprocesso: GTK/AppIndicator precisa da thread principal,
        que aqui pertence ao tkinter. O subprocesso escreve comandos no stdout."""
        if pystray is None:
            return
        try:
            self.tray = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--tray"],
                                         stdout=subprocess.PIPE, text=True)
        except Exception as e:
            self.tray = None
            self.status.set(f"Bandeja indisponível: {e}")
            return
        threading.Thread(target=self.tray_reader, args=(self.tray,), daemon=True).start()

    def tray_reader(self, proc):
        for line in proc.stdout:
            self.q.put(("ui", line.strip()))
        if proc.wait() != 0:  # bandeja morreu: não deixe o app invisível
            self.q.put(("ui", "tray_dead"))

    def on_close(self):
        if self.tray:
            self.withdraw()  # continua na bandeja
        else:
            self.quit_app()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self):
        if self.proc:
            self.proc.terminate()
        if self.tray:
            self.tray.terminate()
        self.destroy()

    # --- helpers
    def refresh_last(self):
        try:
            t = float(LAST_FILE.read_text())
            self.last.set("Última marcação: " + time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(t)))
        except Exception:
            self.last.set("Última marcação: —")

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def save_user(self):
        u = self.user.get().strip()
        if not u:
            messagebox.showwarning("Ponto", "Informe o usuário.")
            return
        write_user(u)
        self.status.set("Usuário salvo.")

    def set_busy(self, busy):
        st = "disabled" if busy else "normal"
        self.btn_bater.configure(state=st)
        self.btn_login.configure(state=st)
        self.btn_cancel.configure(state="normal" if busy else "disabled")

    # --- execução
    def run(self, cmd):
        if self.proc:
            return
        if not read_user():
            if not self.user.get().strip():
                messagebox.showwarning("Ponto", "Informe o usuário antes de continuar.")
                return
            write_user(self.user.get().strip())
        if cmd == "bater" and not messagebox.askyesno("Ponto", "Confirmar marcação do ponto agora?"):
            return
        args = [sys.executable, str(SCRIPT), cmd]
        if cmd == "bater" and self.force.get():
            args.append("--force")
        env = dict(os.environ, PYTHONUNBUFFERED="1", HEADED="1" if self.headed.get() else "0")
        self.mfa.set("")
        self.status.set("Executando…" if cmd == "bater" else "Verificando sessão…")
        self.append(f"$ ponto.py {' '.join(args[2:])}")
        self.set_busy(True)
        self.proc = subprocess.Popen(args, cwd=BASE, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()

    def reader(self, proc):
        for line in proc.stdout:
            self.q.put(("line", line.rstrip()))
        self.q.put(("done", proc.wait()))

    def cancel(self):
        if self.proc:
            self.proc.terminate()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "ui":
                    if val == "quit":
                        self.quit_app()
                        return
                    if val == "tray_dead":
                        self.tray = None
                        self.show()
                        continue
                    self.show()
                    if val == "bater":
                        self.run("bater")
                elif kind == "line":
                    self.append(val)
                    m = MFA_RE.search(val)
                    if m:
                        self.mfa.set(f"Digite {m.group(1)} no Authenticator")
                        self.status.set("Aguardando aprovação no Microsoft Authenticator…")
                else:
                    self.proc = None
                    self.set_busy(False)
                    self.mfa.set("")
                    self.refresh_last()
                    if val == 0:
                        self.status.set("Concluído com sucesso.")
                    else:
                        self.status.set(f"Falhou (código {val}). Veja o log.")
        except queue.Empty:
            pass
        self.after(100, self.poll)


def run_tray():
    """Processo da bandeja: imprime 'show' | 'bater' | 'quit' no stdout."""
    def send(cmd):
        print(cmd, flush=True)

    menu = pystray.Menu(
        pystray.MenuItem("Abrir", lambda *_: send("show"), default=True),
        pystray.MenuItem("Bater ponto", lambda *_: send("bater")),
        pystray.MenuItem("Sair", lambda *_: send("quit")),
    )
    icon = pystray.Icon("ponto", make_icon(), "Ponto", menu)
    parent = os.getppid()

    def watch_parent():  # não fica órfã se o app principal morrer
        while os.getppid() == parent:
            time.sleep(2)
        icon.stop()

    threading.Thread(target=watch_parent, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    if "--tray" in sys.argv:
        run_tray()
        sys.exit(0)
    App(start_hidden="--minimized" in sys.argv).mainloop()
