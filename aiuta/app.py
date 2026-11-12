"""The window they see: one very big button, big text, nothing else.

Press the button (or the space bar), say what you want, and it happens.
A small "Setup" link in the corner opens the family setup page.
"""
from __future__ import annotations

import threading
import tkinter as tk

from . import config
from .brain import Brain
from .setup_server import SetupServer
from .speech import Listener, Speaker


class App:
    def __init__(self):
        self.cfg = config.load()
        self.brain = Brain(self.cfg)
        self._load_ai()
        self.speaker = Speaker(self.cfg["speak_replies"])
        self.listener = None
        self.busy = False
        self.server = SetupServer(on_change=self._config_changed)
        self.server.start(open_browser=False)

        size = int(self.cfg.get("text_size", 28))
        self.root = tk.Tk()
        self.root.title(f"Helper for {self.cfg['person_name']}")
        self.root.geometry("720x520")
        self.root.configure(bg="#faf7f2")

        self.status = tk.Label(self.root, text="Press the button and tell me what you want.",
                               font=("Helvetica", size), wraplength=660, bg="#faf7f2", fg="#1f2328")
        self.status.pack(pady=(30, 20), padx=20)

        self.button = tk.Button(self.root, text="🎤  Talk", font=("Helvetica", size + 14, "bold"),
                                bg="#1f6f5c", fg="white", activebackground="#185a4a",
                                activeforeground="white", relief="flat", padx=40, pady=30,
                                command=self.on_talk)
        self.button.pack(pady=10)

        self.yesno = tk.Frame(self.root, bg="#faf7f2")
        tk.Button(self.yesno, text="Yes", font=("Helvetica", size, "bold"), width=6,
                  command=lambda: self.handle_text("yes")).pack(side="left", padx=12)
        tk.Button(self.yesno, text="No", font=("Helvetica", size, "bold"), width=6,
                  command=lambda: self.handle_text("no")).pack(side="left", padx=12)

        self.heard = tk.Label(self.root, text="", font=("Helvetica", max(14, size - 10)),
                              bg="#faf7f2", fg="#5d6670", wraplength=660)
        self.heard.pack(pady=10)

        setup = tk.Label(self.root, text="Setup (for family)", fg="#5d6670", bg="#faf7f2",
                         cursor="hand2", font=("Helvetica", 11, "underline"))
        setup.pack(side="bottom", anchor="e", padx=12, pady=8)
        setup.bind("<Button-1>", lambda e: self._open_setup())

        self.root.bind("<space>", lambda e: self.on_talk())

    def _load_ai(self):
        self.brain.assistant = None
        if self.cfg["ai"].get("enabled"):
            try:
                from .assistant import Assistant
                self.brain.assistant = Assistant(self.cfg)
            except Exception as e:  # missing package or key: keep working without AI
                print("AI helper is off:", e)

    def _config_changed(self, cfg):
        self.cfg.clear()
        self.cfg.update(cfg)
        self.speaker.enabled = cfg["speak_replies"]
        self.listener = None  # reload with the (possibly new) voice model next time
        self._load_ai()

    def _open_setup(self):
        import webbrowser
        webbrowser.open(self.server.url, new=2)

    def show(self, text: str, question: bool = False):
        self.status.config(text=text)
        if question:
            self.yesno.pack(after=self.button, pady=10)
        else:
            self.yesno.pack_forget()

    def on_talk(self):
        if self.busy:
            return
        self.busy = True
        self.button.config(text="👂  Listening…", bg="#b06a00")
        self.show("I'm listening…", question=bool(self.brain.pending))
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        try:
            if self.listener is None:
                self.listener = Listener(self.cfg["speech_model_path"])
            said = self.listener.listen_once()
        except Exception as e:
            said = ""
            self.root.after(0, self.show, f"The microphone isn't working. Ask the family. ({e})")
        self.root.after(0, self._done_listening, said)

    def _done_listening(self, said: str):
        self.button.config(text="🎤  Talk", bg="#1f6f5c")
        self.busy = False
        if said:
            self.handle_text(said)

    def handle_text(self, said: str):
        self.heard.config(text=f'You said: "{said}"')

        def work():
            result = self.brain.hear(said)
            self.root.after(0, self.show, result.reply, bool(result.question))
            self.speaker.say(result.reply)

        threading.Thread(target=work, daemon=True).start()

    def run(self):
        self.root.mainloop()
        self.server.stop()


def main():
    App().run()
