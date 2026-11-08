"""A re-export, with no tests: other test files still import Bento's `shown` from here. Bento's tests are
in desktop/tests/week/test_bento_*.py, desktop/tests/day/test_bento_day.py and
desktop/tests/month/test_bento_month.py; the helper lives in desktop/tests/day/support_bento.py."""

from desktop.tests.day.support_bento import shown

__all__ = ["shown"]
