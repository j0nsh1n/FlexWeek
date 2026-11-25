"""Report a problem: the maintainer's online form, opened with the version and computer filled in."""

from __future__ import annotations

import platform
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from desktop.native.version import VERSION

# The form's pre-filled link exactly as the form gives it, made with these two sample answers. Empty means
# no form yet, and then the button is not shown.
FORM_LINK = (
    "https://docs.google.com/forms/d/e/1FAIpQLSeA3P9-IWlLc44HPzrNT-FnnEL7D-0FZfTzSXxO9nuhWKJ0rQ/viewform"
    "?usp=pp_url&entry.1113372711=1.4.0&entry.710379005=test"
)
SAMPLE_VERSION = "1.4.0"
SAMPLE_DEVICE = "test"


def form_url(link: str, version: str, device: str) -> str:
    """The pre-filled link with its sample answers replaced by this app's version and this computer."""
    parts = urlsplit(link)
    answers = {SAMPLE_VERSION: version, SAMPLE_DEVICE: device}
    query = [
        (key, answers.get(value, value)) for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


def device_text() -> str:
    """For example "Windows 11" or "Linux 6.8.0 (x86_64)", plain enough for the student to recognise."""
    system = platform.system() or "Unknown system"
    release = platform.release()
    machine = platform.machine()
    text = f"{system} {release}".strip()
    return f"{text} ({machine})" if machine else text


def available() -> bool:
    return bool(FORM_LINK)


def open_form() -> bool:
    return QDesktopServices.openUrl(QUrl(form_url(FORM_LINK, VERSION, device_text())))
