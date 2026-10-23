"""
boot — the login screen ATLAS shows before it loads.

WHY IT RUNS FIRST
    main.py imports modules that decide WHERE to read and write their data at
    import time — config_manager, ninerouter, gemini, audit, skills — and they
    now take that folder from core.profile.base_dir(). So the active account has
    to be chosen BEFORE those imports run. run_login() does that: it shows the
    screen, and on success calls profile.set_active(nick), which sets the
    ATLAS_PROFILE the path modules read. main.py calls it at the very top, right
    after the DPI setup and before `from ui import ...`.

ACCOUNTS
    nickname + password, kept by core.accounts (hashed, never plain text). One
    built-in admin ("admin" / "bialrubi"). Everyone — admin included — gets their
    own data folder under profiles/<nick>/. The admin can later browse the other
    local profiles from the admin panel in the app.

    These accounts are LOCAL to this computer. This screen is a convenience gate
    between people who share one machine, not remote access to anyone else's.
"""
from __future__ import annotations

import sys

from core import accounts, profile


def run_login() -> bool:
    """Show the login/register screen.

    Returns True once an account is active (ATLAS_PROFILE set, data paths ready)
    and False if the window was closed without logging in — the caller should
    then exit without starting ATLAS.
    """
    # A profile already chosen for this process (a relaunch that passed
    # ATLAS_PROFILE, or the admin's "entrar como") is trusted — skip the screen.
    if profile.active():
        return True

    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        # No Qt (headless run, tests): fall through with no profile, i.e. the
        # install-root default. ATLAS then behaves exactly as before login.
        return True

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = _LoginDialog()
    dlg.exec()
    if not dlg.chosen:
        return False
    profile.set_active(dlg.chosen)
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  The dialog
# ─────────────────────────────────────────────────────────────────────────────
_QSS = """
QDialog { background: #00060a; }
#card { background: #010d14; border: 1px solid #1a5c7a; border-radius: 14px; }
#title { color: #00d4ff; font-size: 26px; font-weight: 800; letter-spacing: 6px; }
#sub   { color: #3a8a9a; font-size: 12px; letter-spacing: 1px; }
QLabel { color: #5ab8cc; font-size: 12px; }
QLineEdit {
    background: #00060a; color: #8ffcff; border: 1px solid #0d3347;
    border-radius: 8px; padding: 10px 12px; font-size: 14px;
    selection-background-color: #007a99;
}
QLineEdit:focus { border: 1px solid #00d4ff; }
#msg { font-size: 12px; }
QPushButton {
    border-radius: 8px; padding: 11px 16px; font-size: 13px; font-weight: 700;
}
#enter {
    background: #001f2e; color: #00d4ff; border: 1px solid #0f4060;
}
#enter:hover  { background: #002b3f; border: 1px solid #00d4ff; }
#register {
    background: transparent; color: #00ff88; border: 1px solid #00aa55;
}
#register:hover { background: #00140a; border: 1px solid #00ff88; }
"""


def _build_dialog_cls():
    """Built lazily so importing this module never needs PyQt6 (keeps tests and
    headless runs importing core.boot without a GUI stack)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
        QWidget,
    )

    class _LoginDialog(QDialog):
        def __init__(self) -> None:
            super().__init__()
            self.chosen: str = ""
            self.setWindowTitle("ATLAS")
            self.setFixedSize(420, 430)
            self.setStyleSheet(_QSS)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(24, 24, 24, 24)
            card = QWidget(objectName="card")
            outer.addWidget(card)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(28, 28, 28, 28)
            lay.setSpacing(12)

            title = QLabel("A.T.L.A.S.", objectName="title")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub = QLabel("entre ou registre-se", objectName="sub")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(title)
            lay.addWidget(sub)
            lay.addSpacing(10)

            lay.addWidget(QLabel("Nickname"))
            self.nick = QLineEdit()
            self.nick.setPlaceholderText("seu apelido")
            self.nick.setMaxLength(40)
            lay.addWidget(self.nick)

            lay.addWidget(QLabel("Senha"))
            self.pw = QLineEdit()
            self.pw.setEchoMode(QLineEdit.EchoMode.Password)
            self.pw.setPlaceholderText("••••••")
            self.pw.returnPressed.connect(self._enter)
            lay.addWidget(self.pw)

            self.msg = QLabel("", objectName="msg")
            self.msg.setWordWrap(True)
            self.msg.setMinimumHeight(34)
            lay.addWidget(self.msg)

            row = QHBoxLayout()
            row.setSpacing(10)
            b_enter = QPushButton("Entrar", objectName="enter")
            b_enter.clicked.connect(self._enter)
            b_reg = QPushButton("Registrar", objectName="register")
            b_reg.clicked.connect(self._register)
            row.addWidget(b_enter)
            row.addWidget(b_reg)
            lay.addLayout(row)
            lay.addStretch(1)

            self.nick.setFocus()

        # — helpers —
        def _say(self, text: str, ok: bool = False) -> None:
            self.msg.setStyleSheet(f"color: {'#00ff88' if ok else '#ff3355'};")
            self.msg.setText(text)

        def _enter(self) -> None:
            nick = self.nick.text().strip()
            pw = self.pw.text()
            if not nick:
                self._say("Digite seu nickname.")
                return
            ok, _is_admin, message = accounts.verify(nick, pw)
            if ok:
                self.chosen = accounts.ADMIN_NAME if accounts.is_admin(nick) else nick
                self.accept()
            else:
                self._say(message)

        def _register(self) -> None:
            nick = self.nick.text().strip()
            pw = self.pw.text()
            ok, message = accounts.register(nick, pw)
            if ok:
                # Registered — log straight in, no need to retype.
                self.chosen = nick
                self.accept()
            else:
                self._say(message)

    return _LoginDialog


class _LoginDialog:  # pragma: no cover - thin lazy wrapper
    """Placeholder that becomes the real QDialog subclass on first construction,
    so `from core import boot` never imports PyQt6 by itself."""

    def __new__(cls):
        real = _build_dialog_cls()
        return real()
