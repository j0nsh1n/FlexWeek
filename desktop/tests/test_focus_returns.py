"""Kept so the tests that import `add_homework` from here still find it; the tests of where the
keyboard goes after the week changes are in desktop/tests/week/test_keyboard_returns_to_week.py. No
tests live in this module."""

from desktop.tests.week.support_keyboard_return import add_homework

__all__ = ["add_homework"]
