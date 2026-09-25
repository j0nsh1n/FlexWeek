# Audit 2: using 0.15 as a student would (Claude, 24 September)

Taken over from ChatGPT's unfinished pass (`chatgpt/0-15-ux-audit`, screenshots of first launch,
setup and the homework editor in `docs/0.15/evidence/ux-audit-01/`). This pass read 52 screens at
`a8e0b5a`: every design's Day, Week and Month, One thing, Day dial, the More menu, all five Settings
pages, the block and homework editors and Account, at 1280x860 and at 1150x768 with large text
(`~/.flexweek-ui-harness/scratch/audit/`, made by `scratch/audit_tour.py`). Then the code behind
each thing that looked wrong. Jonathan's own findings are in `owner-findings.md`; where this pass
settles one of them it says so.

## Bugs

1. **New homework is due on Monday, not today.** The editor opens with Due set to the week's
   Monday (`widgets.py:913`, `"due": due or week_start`). Confirms owner finding 6. Default to
   today, or tomorrow when today is nearly over.
2. **Mission opens at midnight.** Its Day and Week show 00:00 to 11:00 on first show, so a student
   sees empty night and has to scroll to the afternoon. Every other design scrolls to now or to the
   first block (`scroll_to` in their `render`); Mission has no `scroll_to` at all.
3. **A short block on sideways hours is three dots.** Timeline's Week at 64 px an hour draws the
   30-minute Dinner as "…" on three lines (Mission the same at its default), because the shared
   painter elides each line to "…" when no word fits and still draws it. When the elided title is
   nothing but "…", draw nothing but the colour stripe. Engine (`canvas.py`, `words`).
4. **The first and last hour labels are cut at the scroll edges** on sideways hours: Timeline's
   Week shows ")8:00" at the left and "24:0" at the right, Mission ":00". Engine (`hour_labels`);
   the label at the visible edge should be pushed inside it, as the block name is.
5. **The tray chip shortens the wrong end.** "Science poster · 1 h …" in Today's app's and Clay's
   Day trays: the length is cut and the title kept whole, so the student loses the one number the
   chip is for. Elide the title first ("Science pos… · 1 h 30 min"), or wrap.
6. **Settings says "FlexWeek 0.14.3".** `desktop/native/version.py` still says 0.14.3; the release
   step must bump it, and the updater compares it.
7. **Retro's notepad clips its deadline lines** at 1150x768 with large text: "History essay Sun 27
   Se". The line should shorten with "…" or wrap.
8. **The More menu has no descriptions**, and "Unfinished" is greyed with nothing to say why. Its
   actions are made with `more_menu.addAction(button.text())` (`window.py:683`) and get no
   `setToolTip`/`setStatusTip`; nor does "Plan my homework" / "Suggest times". Confirms owner
   finding 4. Give each a one-line tooltip, and a disabled one a reason.

## Could not reproduce

- **Times stepping by 5 minutes** (owner finding 1). In code every time box steps by one minute:
  the block editor's Start and End (`17:15` → `17:16` on step, hour step `18:16`, a typed `17:17`
  kept) and the homework editor's set time (`09:00` → `09:01`). Probed offscreen with
  `scratch/time_step_probe.py`. Need to know which box and how it was moved (arrow keys, the
  spinner, the wheel, typing); the desktop's own style may be stepping the wheel.
- **No reminder for a drag-created block** (owner finding 5). The reminder check reads the open
  week's live blocks (`_today_reminder_source`), so a block saved a moment ago is seen; it fires
  when `now - 2 <= start - lead <= now`, polled every `REMINDER_POLL_MS`. Two things can stop it:
  Settings > Alerts > "Reminders" is off by default (see 10 below), and a block whose start is
  already within the lead time when it is saved has its fire time in the past window. To check
  with the clock held: lead 5, a block saved at 17:02 for 17:15, then tick to 17:10.
- **A block's Spotify link playing at its start.** Not a feature: a block's link opens only from
  More > Open Spotify link; only the alarms under Settings > Alerts play a song by themselves. A
  product decision, not a bug: if a block with a link should play it when its reminder fires, say
  so and it becomes work.

## Design and wording

9. **Settings > Appearance & layout is dense** (owner finding 2). The page opens with an
   implementation note ("Timeline has its own colours, under Main view. Set them to Match my look
   to use Look and Accent."), then Animations, then a "Fine-tune" checkbox, then a "Main view"
   label that heads a box within the box holding a dropdown, its description, and a grey table of
   Style rows. Suggest: the note goes (or moves under the colours it is about); "Main view" becomes
   the page's first heading with the design picker; style rows sit flat under it; fine-tune last.
10. **Settings > Alerts mixes two things and hides a switch.** "Alarm sound: Chime [Play], Spotify
    link" sits above "Reminders" with the Reminders checkbox off by default while every control
    under it looks live (Lead minutes, Play a sound, Alert volume with a second "Chime" dropdown and
    [Test]). A student who wants a reminder must find one unchecked box. Suggest: Reminders first,
    on by default after setup asks, its controls greyed while off; alarms as their own group with
    their times, since the page never shows when an alarm rings.
11. **"in 20m" vs "in 20 min".** Today's app's "Next:" line says "(in 20m)"; One thing says "IN 20
    MIN"; Retro's Up next says "in 20 min". One form.
12. **Today's app's unlabelled strip.** Under "Next: …" a white bar reads "History essay 19:00" with
    nothing saying what it is (tonight's pinned homework). A word in front, or fold it into the
    Next line.
13. **Retro shows the same "no time yet" chips twice**, in deadlines.txt and at the foot of the main
    window. Two places to drag from is fine; two copies of the same list is noise on a small
    screen. One or the other.
14. **Clay's fanned Week leans its hour numbers** with the first card. The concept's look; noted
    so no one reports it as a bug.
15. **Account says "Signed in as audit_student. On this device"** with no full stop on the second
    sentence. Trivial.

## Later, footnoted (owner finding 3)

- A first-run tutorial and short guides. Out of 0.15's scope; setup's pages are the nearest thing
  today.

## What passed the eye

Every design's blocks are readable at both sizes; held words, refusals in red, trays and day names
are on screen at 1150x768 with large text; Month is the same grid everywhere and shows every
design's colours; the dial and One thing read cleanly; the editors and Account are clear.
