"""Seeing and using the screen, for the agent.

Instead of sending pictures of the screen to the AI (slow and expensive),
Aiuta reads the screen as text through Windows UI Automation, the same
system screen readers for blind people use. The AI gets a short list like:

    Window: "Inbox - Gmail - Microsoft Edge"
    [1] button "Compose"
    [2] edit "Search mail"
    [3] link "Mary Rossi - Sunday lunch"

and answers "click 1". That is a few hundred words per step, which is why a
very cheap model like Amazon Nova Micro or Lite is enough.

Only works on Windows. Elsewhere the agent can still open things, search and
write emails, but not read or press things on the screen.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

MAX_ELEMENTS = 120
MAX_TEXT_CHARS = 3500
AIUTA_TITLES = ("Aiuta", "Aiuta Setup", "Impostazioni di Aiuta")


@dataclass
class Element:
    id: int
    kind: str          # button, link, edit, checkbox, ...
    name: str
    value: str = ""
    password: bool = False
    handle: object = None  # the real control (Windows only)


@dataclass
class Screen:
    title: str
    elements: list[Element] = field(default_factory=list)
    text: list[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f'Window: "{self.title}"', "Buttons, links and boxes (use the number):"]
        for e in self.elements:
            line = f'[{e.id}] {e.kind} "{e.name}"'
            if e.password:
                line += " (password box: never type here)"
            elif e.value:
                line += f' = "{e.value[:80]}"'
            lines.append(line)
        if self.text:
            lines.append("Text on the screen:")
            total = 0
            for t in self.text:
                if total + len(t) > MAX_TEXT_CHARS:
                    lines.append("…")
                    break
                lines.append(t)
                total += len(t)
        return "\n".join(lines)

    def find(self, element_id: int) -> Element | None:
        for e in self.elements:
            if e.id == element_id:
                return e
        return None


class Desktop:
    """What the agent needs from the computer."""

    available = False

    def read(self) -> Screen:
        raise NotImplementedError

    def current_title(self) -> str:
        return self.read().title

    def click(self, element: Element) -> None:
        raise NotImplementedError

    def type(self, element: Element, text: str) -> None:
        raise NotImplementedError

    def press(self, key: str, screen: Screen) -> None:
        raise NotImplementedError

    def wait(self, seconds: float = 2.0) -> None:
        time.sleep(seconds)

    def compact(self, on: bool) -> None:
        """Shrink Aiuta's own window into a corner (and keep it on top) while the agent works."""


class NoDesktop(Desktop):
    """Used where screen reading isn't available (macOS, Linux)."""

    def read(self) -> Screen:
        return Screen("(screen reading only works on Windows)")


# ---- Windows ---------------------------------------------------------------------

_KINDS = {
    "ButtonControl": "button", "SplitButtonControl": "button", "HyperlinkControl": "link",
    "EditControl": "edit", "CheckBoxControl": "checkbox", "RadioButtonControl": "option",
    "ComboBoxControl": "dropdown", "MenuItemControl": "menu item", "TabItemControl": "tab",
    "ListItemControl": "list item", "TreeItemControl": "item", "DocumentControl": "document",
}
_KEYS = {
    "enter": "{Enter}", "ctrl+enter": "{Ctrl}{Enter}", "tab": "{Tab}", "escape": "{Esc}",
    "page down": "{PageDown}", "page up": "{PageUp}", "up": "{Up}", "down": "{Down}",
}
_IGNORE_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}


def _escape_keys(text: str) -> str:
    return text.replace("{", "\0L").replace("}", "\0R").replace("\0L", "{{}").replace("\0R", "{}}")


class WindowsDesktop(Desktop):
    available = True

    def __init__(self):
        import uiautomation as auto  # only on Windows

        self.auto = auto
        self._window = None
        self._saved_rect = None

    def _target_window(self):
        """The top window that isn't Aiuta itself or the taskbar."""
        for w in self.auto.GetRootControl().GetChildren():
            try:
                if not w.Name or w.ClassName in _IGNORE_CLASSES or w.IsOffscreen:
                    continue
                if w.Name in AIUTA_TITLES or w.Name.startswith(AIUTA_TITLES[0] + " -"):
                    continue
                return w
            except Exception:
                continue
        return None

    def current_title(self) -> str:
        win = self._target_window()
        return win.Name if win is not None else ""

    def read(self) -> Screen:
        win = self._target_window()
        self._window = win
        if win is None:
            return Screen("(no window open)")
        screen = Screen(win.Name)
        seen_text = set()
        visited = 0
        for c, _depth in self.auto.WalkControl(win, includeTop=False, maxDepth=30):
            visited += 1
            if visited > 4000 or len(screen.elements) >= MAX_ELEMENTS:
                break
            try:
                if c.IsOffscreen:
                    continue
                kind = _KINDS.get(c.ControlTypeName)
                name = (c.Name or "").strip()
                if kind and kind != "document":
                    value = ""
                    if kind in ("edit", "dropdown"):
                        try:
                            value = c.GetValuePattern().Value or ""
                        except Exception:
                            value = ""
                    if not name and not value and kind != "edit":
                        continue
                    screen.elements.append(Element(
                        id=len(screen.elements) + 1, kind=kind, name=name[:100], value=value,
                        password=bool(getattr(c, "IsPassword", False)), handle=c))
                elif c.ControlTypeName == "TextControl" and name and name not in seen_text:
                    seen_text.add(name)
                    screen.text.append(name[:300])
            except Exception:
                continue
        return screen

    def _focus_window(self) -> None:
        try:
            if self._window is not None:
                self._window.SetActive()
        except Exception:
            pass

    def click(self, element: Element) -> None:
        c = element.handle
        try:
            c.GetInvokePattern().Invoke()
        except Exception:
            self._focus_window()
            c.Click(simulateMove=False)

    def type(self, element: Element, text: str) -> None:
        c = element.handle
        self._focus_window()
        c.SetFocus()
        try:
            c.GetValuePattern().SetValue(text)
        except Exception:
            self.auto.SendKeys(_escape_keys(text), interval=0.01)

    def press(self, key: str, screen: Screen) -> None:
        self._focus_window()
        self.auto.SendKeys(_KEYS[key])

    def compact(self, on: bool) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Aiuta")
        if not hwnd:
            return
        HWND_TOPMOST, HWND_NOTOPMOST, SWP_SHOWWINDOW = -1, -2, 0x40

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        if on:
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            self._saved_rect = (r.left, r.top, r.right - r.left, r.bottom - r.top)
            sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            w, h = 440, 420
            user32.SetWindowPos(hwnd, HWND_TOPMOST, sw - w - 16, sh - h - 64, w, h, SWP_SHOWWINDOW)
        elif self._saved_rect:
            x, y, w, h = self._saved_rect
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, x, y, w, h, SWP_SHOWWINDOW)
            self._saved_rect = None


def default_desktop() -> Desktop:
    if sys.platform.startswith("win"):
        try:
            return WindowsDesktop()
        except Exception:
            pass
    return NoDesktop()


# ---- For tests ---------------------------------------------------------------------

class FakeDesktop(Desktop):
    """A pretend screen for tests: a list of screens it moves through as things are pressed."""

    available = True

    def __init__(self, title: str, elements: list[tuple], text: list[str] | None = None):
        self.title = title
        self.elements = [Element(i + 1, kind, name, password=(kind == "password"))
                         for i, (kind, name) in enumerate(elements)]
        for e in self.elements:
            if e.kind == "password":
                e.kind = "edit"
        self.text = text or []
        self.log: list[tuple] = []

    def read(self) -> Screen:
        self.log.append(("read",))
        return Screen(self.title, list(self.elements), list(self.text))

    def current_title(self) -> str:
        return self.title

    def click(self, element: Element) -> None:
        self.log.append(("click", element.name))

    def type(self, element: Element, text: str) -> None:
        self.log.append(("type", element.name, text))

    def press(self, key: str, screen: Screen) -> None:
        self.log.append(("press", key))

    def wait(self, seconds: float = 2.0) -> None:
        self.log.append(("wait",))
