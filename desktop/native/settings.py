"""Focus panel, restore points and account dialogs."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QGuiApplication,
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPalette,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop.native.remind import ALARM_SNOOZE_MIN
from desktop.native.settings_copy import (
    ABOUT_HERE,
    ABOUT_LINE,
    ACCOUNT_CODES_NOTE,
    ACCOUNT_DATA_NOTE,
    ACCOUNT_PASSWORD_NOTE,
    HELP_KEYS,  # noqa: F401
    HELP_PLANNING,
    HELP_SCREENS,
    RESTORE_FIRST,
    SPORT_FALLBACK,  # noqa: F401
    SPOTIFY_TONE_NOTE,  # noqa: F401
    first_lines,
    help_keys,
    keys_words,
    recovery_status,
    restore_row,
    restore_summary,
    transfer_summary,
)
from desktop.native.spotify import open_in_app
from desktop.native.tokens import SPACING
from desktop.native.version import VERSION
from desktop.native.weekmodel import hhmm_text
from desktop.native.widgets import (
    ROUTINE_LIST_HEIGHT,
    SHEET_FORM,
    SHEET_LIST,
    Dialog,
    FitScroll,
    FlowLayout,
    Form,
    PasswordField,
    bare,
    caption_above,
    sheet_button,
    sheet_footer,
    sheet_section,
)

UPDATE_MIN_WIDTH = 420
ALARM_MIN_WIDTH = 380
ALARM_PAD = 20
ALARM_GAP = 12
ALARM_BUTTON_HEIGHT = 44
SECTION_GAP = 14
LOGO = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
ABOUT_LOGO_PX = 56
# How far the words fade out at a scroll edge with more past it.
FADE_PX = 24


def _page_button(words: str, name: str) -> QPushButton:
    """A button that opens something else or acts on the side. Outlined and as wide as its words, since
    Done is the one filled button in Settings; stretched and filled, each was the loudest thing on its
    page, and as words alone none looked like a button."""
    made = QPushButton(words)
    made.setObjectName(name)
    made.setProperty("outline", True)
    made.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return made


def _heading(words: str) -> QLabel:
    """A card's title, so eighteen settings stop reading as one list."""
    made = QLabel(words)
    made.setObjectName("prefsHeading")
    return made




class RestoreDialog(Dialog):
    def __init__(
        self,
        parent: QWidget | None,
        points: list[dict],
        preview: dict | None,
        storage: dict | None,
    ) -> None:
        super().__init__(parent, sheet=True)
        self.setObjectName("restoreDialog")
        self.selected_id: str | None = None
        layout = self.card_body("Restore points", SHEET_LIST)
        location = QLabel((storage or {}).get("label") or "Backup location unavailable")
        location.setObjectName("storageLocation")
        location.setWordWrap(True)
        layout.addWidget(location)
        self.label = QLineEdit()
        self.label.setObjectName("restoreLabel")
        self.label.setAccessibleName("Restore point name")
        layout.addWidget(caption_above("Restore point name", self.label))
        layout.addWidget(self.label)
        create = QPushButton("Save restore point")
        create.setProperty("outlined", True)
        create.setObjectName("restoreCreate")
        create.clicked.connect(self._create)
        layout.addWidget(create)
        self.list = QListWidget()
        self.list.setObjectName("restoreList")
        self.list.setFixedHeight(ROUTINE_LIST_HEIGHT)
        for point in points:
            item = QListWidgetItem(restore_row(point))
            item.setData(Qt.ItemDataRole.UserRole, point.get("id"))
            self.list.addItem(item)
        layout.addWidget(self.list)
        self.summary = QLabel()
        self.summary.setObjectName("restorePreviewSummary")
        self.summary.setText(restore_summary(preview))
        layout.addWidget(self.summary)
        preview_btn = QPushButton("Preview")
        preview_btn.setObjectName("restorePreview")
        preview_btn.setProperty("outlined", True)
        preview_btn.clicked.connect(self._preview)
        restore_btn = QPushButton("Restore")
        restore_btn.setObjectName("restoreApply")
        restore_btn.clicked.connect(self._restore)
        sheet_footer(layout, preview_btn, restore_btn, divided=True)
        self.action: str | None = None
        self.create_label = ""
        preview_id = None if not preview else preview.get("id")
        if preview_id:
            for index in range(self.list.count()):
                item = self.list.item(index)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == preview_id:
                    self.list.setCurrentRow(index)
                    break

    def _selected(self) -> str | None:
        item = self.list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _create(self) -> None:
        self.action = "create"
        self.create_label = self.label.text().strip()
        self.accept()

    def _preview(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.summary.setText(RESTORE_FIRST)
            return
        self.selected_id = chosen
        self.action = "preview"
        self.accept()

    def _restore(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.summary.setText(RESTORE_FIRST)
            return
        self.selected_id = chosen
        self.action = "restore"
        self.accept()


class AccountDialog(Dialog):
    def __init__(self, parent: QWidget | None, remaining: int | None, storage: dict | None) -> None:
        super().__init__(parent, sheet=True)
        self.setObjectName("accountDialog")
        self.action: str | None = None
        layout = self.card_body("Manage account", SHEET_FORM)
        where = "your FlexWeek server" if (storage or {}).get("mode") == "hosted" else "this computer"
        info = QLabel(
            f"Signed in as {(storage or {}).get('username') or ''}. "
            f"Your week is saved on {where}, under this account."
        )
        info.setWordWrap(True)
        info.setObjectName("accountLocation")
        layout.addWidget(info)
        remaining_text = recovery_status(remaining)
        status = QLabel(remaining_text)
        status.setObjectName("recoveryCount")
        status.setProperty("problem", remaining == 0)
        # One body that scrolls past 90 % of the window, its answers fixed under it. Sections, each about
        # one thing, with every label above its field (#70: the two password boxes were drawn over each
        # other and the red action was cut off).
        left = Qt.AlignmentFlag.AlignLeft
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACING[2])
        sheet_section(column, "Password", ACCOUNT_PASSWORD_NOTE)
        form = Form(stacked=True)
        self.current_password = PasswordField()
        self.current_password.setObjectName("currentPassword")
        form.addRow("Current password", self.current_password)
        self.new_password = PasswordField()
        self.new_password.setObjectName("newPassword")
        form.addRow("New password", self.new_password)
        column.addLayout(form)
        # Replace password is the answer to the two fields above; the rest open something else.
        column.addWidget(self._action("Replace password", "changePassword", "password", False), 0, left)
        sheet_section(column, "Recovery codes", ACCOUNT_CODES_NOTE)
        column.addWidget(status)
        column.addWidget(self._action("Replace recovery codes", "replaceCodes", "codes"), 0, left)
        sheet_section(column, "Your data", ACCOUNT_DATA_NOTE)
        files = FlowLayout()
        for words, name, action in (
            ("Export backup file", "exportAccount", "export"),
            ("Import backup file", "importAccount", "import"),
            ("Export week", "exportWeek", "week"),
            ("Export day", "exportDay", "day"),
            ("Import week or day file", "importFile", "import-week"),
        ):
            files.addWidget(self._action(words, name, action))
        column.addLayout(files)
        # Deleting is in red, apart from the rest, and shown whole: an outlined button, not words.
        delete = QPushButton("Delete account")
        delete.setObjectName("deleteAccount")
        delete.setProperty("action", "delete")
        delete.setProperty("outlined", True)
        delete.setProperty("danger", True)
        delete.setAutoDefault(False)
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(self._set)
        column.addSpacing(SPACING[2])
        column.addWidget(delete, 0, left)
        layout.addWidget(FitScroll(body, "accountScroll"), 1)
        close = sheet_button("Close", "outlined", "accountClose")
        close.clicked.connect(self.reject)
        sheet_footer(layout, close, divided=True)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

    def _action(self, words: str, name: str, action: str, outlined: bool = True) -> QPushButton:
        button = QPushButton(words)
        button.setObjectName(name)
        button.setProperty("action", action)
        button.setProperty("outlined", outlined)
        button.clicked.connect(self._set)
        return button

    def _set(self) -> None:
        self.action = self.sender().property("action")
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            self.reject()
            return
        super().keyPressEvent(event)


class AlarmRingDialog(QDialog):
    def __init__(self, parent: QWidget | None, alarm: dict, spotify: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Alarm")
        self.setModal(True)
        self.snoozed = False
        self.open_spotify = False
        self._url = spotify
        # It came up 209px wide, which is smaller than a notification and easy to miss. An alarm is
        # the one thing in the app that is meant to interrupt, so it is given room to be seen.
        self.setMinimumWidth(ALARM_MIN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ALARM_PAD, ALARM_PAD, ALARM_PAD, ALARM_PAD)
        layout.setSpacing(ALARM_GAP)
        title = QLabel(alarm.get("name") or "Alarm")
        title.setObjectName("alarmTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        ringing = "Starting now" if alarm.get("block") else "Alarm is ringing"
        when = str(alarm.get("time") or "")
        detail = QLabel(f"{hhmm_text(when) if when else ''} · {ringing}")
        detail.setObjectName("alarmDetail")
        layout.addWidget(detail)
        layout.addSpacing(ALARM_GAP)
        self.playing = QLabel()
        self.playing.setObjectName("alarmPlaying")
        self.playing.setWordWrap(True)
        self.playing.hide()
        layout.addWidget(self.playing)
        if spotify:
            link = QPushButton("Open in Spotify")
            link.setObjectName("alarmOpenSpotify")
            link.setMinimumHeight(ALARM_BUTTON_HEIGHT)
            link.clicked.connect(self._spotify)
            layout.addWidget(link)
        snooze = QPushButton(f"Snooze {ALARM_SNOOZE_MIN} minutes")
        snooze.setObjectName("alarmSnooze")
        snooze.setProperty("quiet", True)
        snooze.clicked.connect(self._snooze)
        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("alarmDismiss")
        dismiss.setDefault(True)
        dismiss.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.setSpacing(ALARM_GAP)
        for button in (snooze, dismiss):
            button.setMinimumHeight(ALARM_BUTTON_HEIGHT)
            row.addWidget(button)
        layout.addLayout(row)

    def _snooze(self) -> None:
        self.snoozed = True
        self.accept()

    def _spotify(self) -> None:
        self.open_spotify = True
        if self._url:
            open_in_app(self._url)

    def show_playing(self, words: str) -> None:
        """What Spotify is playing for this alarm, once it is heard."""
        self.playing.setText(words)
        self.playing.show()


class TransferPreviewDialog(QDialog):
    def __init__(self, parent: QWidget | None, preview: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import backup file?")
        layout = QVBoxLayout(self)
        source = str(preview.get("source_username") or "another account")
        for words, name in (
            (f"From {source}'s backup: {transfer_summary(preview)}", "transferSummary"),
            ("FlexWeek saves a restore point first, so you can go back.", "transferRestoreNote"),
        ):
            layout.addWidget(_line(words, name))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setProperty("quiet", True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _line(words: str, name: str) -> QLabel:
    made = QLabel(words)
    made.setObjectName(name)
    made.setWordWrap(True)
    return made


def keycaps(marked: str) -> QWidget:
    """A shortcut drawn as keys: each key in brackets a keycap, the words between them plain."""
    row = QWidget()
    row.setObjectName("helpKey")
    row.setAccessibleName(keys_words(marked))
    line = QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(4)
    for part in re.split(r"(\[[^\]]+\])", marked):
        if not part.strip():
            continue
        cap = part.startswith("[")
        made = QLabel(part[1:-1] if cap else part.strip())
        made.setObjectName("helpKeycap" if cap else "helpKeyJoin")
        made.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # At the top of the row, at their own height: stretched to a two-line description they were
        # drawn as tall slabs.
        line.addWidget(made, 0, Qt.AlignmentFlag.AlignTop)
    line.addStretch(1)
    return row


class ScrollFade(QWidget):
    """The words fading out at one edge of a scroll area while there is more past it, so a cut line
    reads as more to scroll to, not as the end."""

    def __init__(self, area: QScrollArea, top: bool) -> None:
        super().__init__(area.viewport())
        self.setObjectName("scrollFadeTop" if top else "scrollFadeBottom")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._area, self._top = area, top
        bar = area.verticalScrollBar()
        bar.valueChanged.connect(self._follow)
        bar.rangeChanged.connect(self._follow)
        area.viewport().installEventFilter(self)
        self._follow()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize:
            self._follow()
        return False

    def _follow(self, *_args: object) -> None:
        view = self._area.viewport()
        self.setGeometry(0, 0 if self._top else view.height() - FADE_PX, view.width(), FADE_PX)
        bar = self._area.verticalScrollBar()
        self.setVisible(bar.value() > bar.minimum() if self._top else bar.value() < bar.maximum())
        self.raise_()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        # The card the words sit on, not the window: a sheet's window is only room for its shadow.
        page = self._area.parentWidget().palette().color(QPalette.ColorRole.Window)
        clear = QColor(page)
        clear.setAlpha(0)
        ramp = QLinearGradient(0, 0, 0, self.height())
        ramp.setColorAt(0, page if self._top else clear)
        ramp.setColorAt(1, clear if self._top else page)
        painter = QPainter(self)
        painter.fillRect(self.rect(), ramp)
        painter.end()


def _logo(side: int) -> QLabel:
    ratio = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
    made = QLabel()
    made.setObjectName("aboutLogo")
    made.setFixedSize(side, side)
    picture = QPixmap(str(LOGO))
    if not picture.isNull():
        picture = picture.scaled(
            round(side * ratio),
            round(side * ratio),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        picture.setDevicePixelRatio(ratio)
        made.setPixmap(picture)
    return made


class AboutDialog(Dialog):
    _pin_top = True

    def __init__(self, parent: QWidget | None, storage: dict | None, folder: str) -> None:
        super().__init__(parent, sheet=True)
        layout = self.card_body("About FlexWeek")
        brand = QHBoxLayout()
        brand.setSpacing(SECTION_GAP)
        brand.addWidget(_logo(ABOUT_LOGO_PX))
        brand.addWidget(_line(f"FlexWeek {VERSION}", "aboutVersion"), 1)
        layout.addLayout(brand)
        layout.addSpacing(SECTION_GAP // 2)
        layout.addWidget(_line(ABOUT_LINE, "aboutWhat"))
        if (storage or {}).get("mode") == "hosted":
            saved = _line(
                "Your week is saved on your FlexWeek server, "
                f"{(storage or {}).get('origin') or ''}, under this account.",
                "aboutWhere",
            )
            saved.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(saved)
        else:
            # The folder as a button, not a path: a path is read, copied and pasted into a file
            # manager, and a student only ever wants to look inside it.
            layout.addWidget(_line(ABOUT_HERE, "aboutWhere"))
            open_folder = _page_button("Open folder", "aboutOpenFolder")
            open_folder.setToolTip(folder)
            open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
            layout.addWidget(open_folder)
        layout.addSpacing(SPACING[3])


class HelpDialog(Dialog):
    """Enough to find your way: the screens two by two, then the keys, drawn as keycaps. A list's sheet,
    600 wide (5.1 A of 0.17.2), so the shortcuts are one column: beside the screens, their words wrapped
    a word or two to a line."""

    _pin_top = True

    def __init__(
        self,
        parent: QWidget | None,
        switches: tuple[bool, bool] = (True, False),
        *,
        material: bool = False,
    ) -> None:
        """`switches` is (Number keys on, Letter keys on); `material` is True when Help is opened from
        Material, whose keys differ from the Widgets looks'."""
        super().__init__(parent, sheet=True)
        layout = self.card_body("Help", SHEET_LIST)
        # Close has no focus on a click (it would be where typing starts) but Tab reaches it, so the
        # keyboard has somewhere to go and shows where it is.
        self.findChild(QPushButton, "sheetClose").setFocusPolicy(Qt.FocusPolicy.TabFocus)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SECTION_GAP // 2)
        column.addWidget(_heading("How planning works"))
        column.addWidget(_line(HELP_PLANNING, "helpPlanning"))
        column.addSpacing(SECTION_GAP // 2)
        column.addWidget(_heading("The screens"))
        screens = QGridLayout()
        screens.setSpacing(SECTION_GAP // 2)
        for index, (name, words) in enumerate(HELP_SCREENS):
            card = QFrame()
            card.setObjectName("helpCard")
            inside = QVBoxLayout(card)
            # The frame's own padding is the card's margin; the layout's default doubled it.
            inside.setContentsMargins(4, 2, 4, 2)
            inside.setSpacing(2)
            title = QLabel(name)
            title.setObjectName("helpScreenName")
            inside.addWidget(title)
            inside.addWidget(_line(words, f"helpScreen{index}"))
            inside.addStretch(1)
            screens.addWidget(card, index // 2, index % 2)
        column.addLayout(screens)
        column.addSpacing(SECTION_GAP // 2)
        column.addWidget(_heading("Keyboard shortcuts"))
        # A form, not a grid: a grid gave a two-line description one line and a bit, and cut it.
        key_list = bare(QWidget())
        key_list.setObjectName("helpKeys")
        keys = QFormLayout(key_list)
        keys.setContentsMargins(0, 0, 0, 0)
        keys.setHorizontalSpacing(SECTION_GAP)
        keys.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for key, what in help_keys(*switches, material=material):
            keys.addRow(keycaps(key), _line(what, "helpKeyDoes"))
        column.addWidget(key_list)
        column.addSpacing(SPACING[3])
        column.addStretch(1)
        # A dialog's minimum counts a wrapped line as one line, so at large text on a laptop, Help at
        # its minimum squeezed the shortcuts to half their height. A scroll area gives the words the
        # height they need at the width they get, and the sheet fits its window.
        area = FitScroll(body, "helpScroll")
        self.fades = (ScrollFade(area, top=True), ScrollFade(area, top=False))
        layout.addWidget(area, 1)


class UpdateDialog(QDialog):
    """A newer FlexWeek exists. Says what it is, and does nothing until the student chooses."""

    def __init__(self, parent: QWidget | None, update: dict, current: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Update FlexWeek")
        self.setModal(True)
        self.setObjectName("updateDialog")
        self.setMinimumWidth(UPDATE_MIN_WIDTH)
        self.choice = "later"
        self.skip_this = False
        layout = QVBoxLayout(self)
        heading = QLabel(f"FlexWeek {update['version']} is ready")
        heading.setObjectName("updateHeading")
        layout.addWidget(heading)
        detail = QLabel(f"You have {current}. Updating keeps your account and your weeks.")
        detail.setObjectName("updateDetail")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        notes = first_lines(update.get("notes") or "")
        if notes:
            body = QLabel(notes)
            body.setObjectName("updateNotes")
            body.setWordWrap(True)
            layout.addWidget(body)
        self.status = QLabel("")
        self.status.setObjectName("updateStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setObjectName("updateProgress")
        self.bar.setVisible(False)
        layout.addWidget(self.bar)
        row = QHBoxLayout()
        self.install = QPushButton("Update now")
        self.install.setObjectName("updateInstall")
        self.install.setDefault(True)
        self.install.clicked.connect(self._install)
        later = QPushButton("Not now")
        later.setObjectName("updateLater")
        later.setProperty("quiet", True)
        later.clicked.connect(self.reject)
        skip = QPushButton("Skip this version")
        skip.setObjectName("updateSkip")
        skip.setFlat(True)
        skip.clicked.connect(self._skip)
        for button in (self.install, later):
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(skip)

    def _install(self) -> None:
        self.choice = "install"
        self.install.setEnabled(False)
        self.bar.setVisible(True)
        self.status.setText("Downloading…")

    def _skip(self) -> None:
        self.skip_this = True
        self.reject()

    def show_progress(self, got: int, total: int) -> None:
        self.bar.setMaximum(max(total, 0))
        self.bar.setValue(got)

    def show_problem(self, why: str) -> None:
        self.bar.setVisible(False)
        self.install.setEnabled(True)
        self.status.setText(why)
