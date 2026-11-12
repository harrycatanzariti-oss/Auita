"""The agent's safety rules, in one place so they are easy to read and review.

1. It stops completely on bank, payment and sign-in pages, and never reads
   them to the AI.
2. It never types into password boxes.
3. Before pressing anything that sends, buys, pays, deletes, posts or can't
   be undone, it asks the person "Shall I …?" and waits for a yes.
4. In "show me" mode it never presses or types anything at all.

These checks run in Aiuta's own code, not in the AI, so a confused or
tricked AI can't skip them.
"""
from __future__ import annotations

import re

# Window titles where the agent stops. Several languages, lower case.
_BLOCKED = [
    r"bank", r"banking", r"banca", r"banco", r"banque", r"sparkasse", r"credit union",
    r"paypal", r"payment", r"pagamento", r"pago", r"paiement", r"zahlung",
    r"checkout", r"cassa", r"credit card", r"carta di credito", r"tarjeta",
    r"password", r"sign[ -]?in", r"log[ -]?in", r"accedi", r"accesso", r"anmelden",
    r"iniciar sesi[oó]n", r"connexion", r"verification code", r"codice di verifica",
    r"bitcoin", r"crypto", r"wallet", r"gift ?card", r"buoni regalo",
]
BLOCKED_TITLE = re.compile(r"(?:^|\W)(?:" + "|".join(_BLOCKED) + r")(?:\W|$)", re.IGNORECASE)

# Buttons that need a "yes" first. Several languages, lower case.
_RISKY = [
    r"send", r"invia", r"inviare", r"enviar", r"envoyer", r"senden", r"absenden",
    r"buy", r"purchase", r"pay", r"order", r"place order", r"checkout", r"donate", r"subscribe",
    r"compra", r"acquista", r"paga", r"ordina", r"comprar", r"pagar", r"acheter", r"payer",
    r"kaufen", r"bezahlen", r"bestellen",
    r"delete", r"remove", r"discard", r"erase", r"elimina", r"cancella", r"rimuovi",
    r"eliminar", r"borrar", r"supprimer", r"löschen", r"entfernen",
    r"confirm", r"conferma", r"confirmar", r"confirmer", r"bestätigen",
    r"submit", r"post", r"publish", r"share", r"reply all", r"forward",
    r"pubblica", r"condividi", r"inoltra", r"publicar", r"compartir", r"publier", r"partager",
    r"transfer", r"trasferisci", r"bonifico", r"transferir", r"virement", r"überweisen",
    r"install", r"installa", r"accept", r"accetta", r"allow", r"consenti",
]
RISKY_NAME = re.compile(r"(?:^|\W)(?:" + "|".join(_RISKY) + r")(?:\W|$)", re.IGNORECASE)

# Windows where pressing Enter sends something.
SENDING_WINDOW = re.compile(
    r"whatsapp|gmail|outlook|mail|messenger|messages|telegram|signal|teams|skype|posta|"
    r"facebook|instagram|x\.com|twitter",
    re.IGNORECASE,
)
SENDING_KEYS = {"enter", "ctrl+enter"}


def is_blocked(window_title: str) -> bool:
    return bool(BLOCKED_TITLE.search(window_title or ""))


def is_risky_button(name: str) -> bool:
    return bool(RISKY_NAME.search(name or ""))


def is_risky_key(key: str, window_title: str) -> bool:
    return key in SENDING_KEYS and bool(SENDING_WINDOW.search(window_title or ""))
