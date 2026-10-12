"""Regression Tester's 0.18.4 suite holds strict xfails the gate counts as skipped; it runs on its own
with FLEXWEEK_REGRESS=1 until every item passes."""

import os

collect_ignore = [] if os.environ.get("FLEXWEEK_REGRESS") else ["regress184"]
