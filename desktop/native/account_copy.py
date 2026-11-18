"""What the sign-in, account creation, recovery codes and password reset screens say."""

from __future__ import annotations

RECOVERY_KEEP = "Keep this file somewhere private. Anyone who has it can reset your password."

RECOVERY_WAIT = "Tick the box above to continue."

# One heading on the sign-in card, the same on a first launch and on a return, and what the page is for
# when making an account.
SIGN_IN_HEADING = "Sign in"

CREATE_HEADING = "Create your account"
CREATE_NOTE = (
    "FlexWeek fits homework around school and sports. "
    "Your week is saved on this computer, under this account. "
    "Export a backup file now and then (Settings > This computer > Manage account)."
)
RESET_HEADING = "Reset your password"
RESET_NOTE = (
    "Use one of the recovery codes you saved when you made your account. Lost them too? Create a new "
    "account and import a backup file, or start fresh."
)


RECOVERY_COPY = "Copy"
RECOVERY_SAVE = "Save…"
RECOVERY_FILE = "flexweek-recovery-codes.txt"
# How long Copy says Copied, and Save says Saved.
RECOVERY_SAID_MS = 2000
