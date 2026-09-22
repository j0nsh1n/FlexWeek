"""The words the solver hands the student."""

from backend.explain import slack_sentence


def test_a_slack_sentence_uses_the_apps_lengths_and_needs_no_colon_of_its_own() -> None:
    """Shown as "Chem lab report: <sentence>". It used to open with "Very little room:", so the line
    had two colons, and it said "29m" where the rest of the app says "29 min"."""
    assert slack_sentence(29, "danger") == "Finishes only 29 min before it is due."
    assert slack_sentence(135, "tight") == "Finishes 2 h 15 min before it is due."
    assert slack_sentence(300, "ok") == "Finishes 5 h before it is due."
    assert slack_sentence(0, "danger") == "Finishes right when it is due."
