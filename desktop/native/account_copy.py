"""What the sign-in, account creation, recovery codes and password reset screens say."""

from __future__ import annotations

RECOVERY_KEEP = "Keep this file somewhere private. Anyone who has it can reset your password."

RECOVERY_WAIT = "Turn on “I have saved these codes” to continue."

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

# Said without the system's own words, which a student cannot act on.
READ_FAILED = "Couldn't open that file. Choose a FlexWeek backup file (it ends in .json)."
READ_WEEK_FAILED = "Couldn't open that file. Choose a FlexWeek week or day file (it ends in .json)."
WRITE_FAILED = "Couldn't save there. Choose another folder, like Documents."
ACCOUNT_SAVED = "Saved your backup file to {path}. Keep it private: it has all your weeks and homework."
REPLACE_WEEK_QUESTION = (
    "Replace everything in {week} with this file? Other weeks aren't changed. You can undo this."
)
DELETE_ACCOUNT_QUESTION = (
    "Delete the account {name}? Every week, all your homework and your settings are removed "
    "from {where}. This can't be undone."
)
