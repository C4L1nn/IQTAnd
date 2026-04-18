"""Sleep timer menu."""

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from core.constants import BORDER_COLOR, TEXT_MUTED
from core.theme import get_accent


def open_sleep_dialog(app):
    """Open the localized sleep timer menu."""
    acc = get_accent()
    t = app._tr

    menu = QMenu()
    menu.setStyleSheet(f"""
        QMenu {{
            background: #1A1A2E;
            border: 1px solid {acc}44;
            border-radius: 12px;
            padding: 6px 0;
            color: white;
        }}
        QMenu::item {{
            padding: 10px 20px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 8px;
            margin: 1px 4px;
        }}
        QMenu::item:selected {{
            background: {acc}28;
            color: {acc};
        }}
        QMenu::item:disabled {{
            color: {TEXT_MUTED};
        }}
        QMenu::separator {{
            height: 1px;
            background: {BORDER_COLOR};
            margin: 4px 10px;
        }}
    """)

    if app._sleep_timer.isActive():
        rem = app._sleep_timer.remainingTime() // 1000
        m, s = rem // 60, rem % 60
        status_act = menu.addAction(t("sleep.remaining", time=f"{m}:{s:02d}"))
        status_act.setEnabled(False)
        menu.addSeparator()

    options = [
        (t("sleep.option_minutes", count=15), 15 * 60),
        (t("sleep.option_minutes", count=30), 30 * 60),
        (t("sleep.option_minutes", count=60), 60 * 60),
        (t("sleep.option_minutes", count=90), 90 * 60),
    ]
    for label, secs in options:
        act = menu.addAction(label)

        def _pick(checked=False, s=secs, lbl=label):
            app._sleep_timer.stop()
            app._sleep_timer.start(s * 1000)
            app.lbl_sleep.show()
            app.sig.notify.emit(t("sleep.toast_set", label=lbl))

        act.triggered.connect(_pick)

    menu.addSeparator()
    cancel_act = menu.addAction(t("sleep.cancel"))

    def _cancel(checked=False):
        if app._sleep_timer.isActive():
            app._sleep_timer.stop()
            app.lbl_sleep.hide()
            app.sig.notify.emit(t("sleep.toast_cancelled"))

    cancel_act.triggered.connect(_cancel)

    menu.exec(QCursor.pos())
