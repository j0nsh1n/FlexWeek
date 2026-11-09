"""The rig's and the renderer's own tests get the desktop tests' cleanup: a widget left for the garbage
collector or a window left showing fails the test that left it, not whichever desktop test the same worker
runs next."""

from desktop.tests.conftest import (  # noqa: F401
    no_window_is_left_for_the_garbage_collector,
    no_window_is_left_showing,
)
