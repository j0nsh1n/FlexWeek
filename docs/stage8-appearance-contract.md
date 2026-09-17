# Contract: appearance packs, accent and motion

Status: proposed. Needs owner approval before any spec.md change.

Claude owns the browser/desktop frontend. Backend preference fields are a
shared change: the model lives in `backend/app.py`. Both clients continue to
use the same HTML, CSS and JavaScript frontend.

This contract is based on `feat/0-11-seamless` at `3157f1d`, which already
ships the motion levels described below as a device-only setting.

Sections 1, 2, 3, 4 and 5 were drafted by GLM through OpenCode against briefs
that carried the facts inline. Every enum member, file path, test name and
numeric bound in them was checked against the source afterwards, and the
corrections are noted where they were made. GLM's first draft of section 3
invented pack and accent names that appear nowhere in this project; those are
replaced here.

## Goal

A student picks one of five theme packs: System, Light frost, Dark frost, Nocturne or Slate. A pack sets the background, the chrome, the accent and the default motion level together, so the whole look is one choice.
When it is built, a student can also open the Customize submenu and set their own accent, optionally apply that accent to category chips, and set Motion to Off, Normal or Extra.
Their accent and motion choices override the pack defaults. Motion Off behaves exactly like the device's reduced-motion setting.

## 1. Theme packs

The app today has a single theme choice with three values.
"system" follows the device's light or dark setting, "slate" is shown to students as Light, and "nocturne" is shown as Dark.
The stylesheet reads `<html data-theme>` and only ever sees "slate" or "nocturne". Both are already frosted looks built from backdrop-filter, with a solid fallback when blur is unavailable.

The five packs map onto that like this:

- **System** is the existing "system" value. Its background and chrome follow the device, resolving to the slate or nocturne stylesheet; its accent and default motion are its own.
- **Nocturne** and **Slate** are the existing "nocturne" and "slate" values, presented under their own names.
- **Light frost** and **Dark frost** are the owner's decision. The facts do not settle it: the pack list names both Slate and Light frost, which could mean two distinct looks, or one look with its old and new names side by side.

The decision matters because the answers are different sizes of work.
If Light frost and Dark frost are new names for Slate and Nocturne, this is a relabelling: students see new words for the same two frosted looks, and `<html data-theme>` keeps working unchanged.
If they are new token sets, each needs its own background, chrome, accent and motion default, and the stylesheet needs a value it understands for them, because today it only ever sees "slate" or "nocturne".
Only the owner can say which it is.

What a pack sets:

- the background
- the chrome
- the accent
- the default motion level

What a pack does not touch:

- a student's own accent and motion choices, which override the pack defaults
- the solid fallback that shows when blur is unavailable
- the animation of anything frosted, because recompositing backdrop-filter flickers on Windows

## 2. The Customize submenu

The submenu is collapsed by default. It holds exactly three controls, no more.

- **Accent colour.** Sets the accent the app uses, overriding the pack default. It does not recolour any surface on its own, and it never touches the background or the chrome.
- **Use the accent for category chips.** An optional toggle. On, category chips take the accent colour. Off, which is the default, chips keep their normal colours. It changes nothing else.
- **Motion.** Off, Normal or Extra, written to `<html data-motion>`. Today it is
  stored on the device only; this contract moves it onto the account in section 3.4,
  and open decision 5 covers what happens to a level a device already holds.
  - Off must behave exactly like the system prefers-reduced-motion setting. Nothing moves.
  - Normal fades the calendar between Week, Day and Month.
  - Extra adds a short rise on the view change and pops in work a plan just placed.
  - There are no blur sliders and no per-widget curves, and nothing frosted is animated, because recompositing backdrop-filter flickers on Windows.

## 3. New preference fields

Drafted by GLM, with the enum members corrected: GLM proposed pack and accent
names that appear nowhere in this project, so they are replaced by the owner's
five packs and by an open question for the accent.

Every field follows the pattern the model already uses: a default plus an
`exclude_if` that drops the field from the response while it holds that
default. An old client that never sends the key still validates, and never
meets it on the way back. `extra="forbid"` is unchanged, so a misspelled key is
still a 422.

### 3.1 Theme pack

```python
theme_pack: Literal["system", "light-frost", "dark-frost", "nocturne", "slate"] = Field(
    default="system", exclude_if=lambda value: value == "system"
)
```

The bound is membership in the Literal; there is no range to state. Whether
this field sits beside `theme` or replaces it is open decision 2. As written it
sits beside `theme`: `theme` keeps owning the light/dark axis that
`<html data-theme>` reads, and the pack selects the look layered on top.

The default is excluded from responses, so an old client never receives a
`theme_pack` key and keeps rendering exactly as it does today.

### 3.2 Accent colour

```python
accent: Literal[...] = Field(default="default", exclude_if=lambda value: value == "default")
```

**A bounded set of named accents, not a free hex string.** A regex only proves a
string is hex-shaped. `frontend/tests/theme-tokens.test.mjs` already asserts the
accent sits at a colour distance of at least 15 from all eight category colours
in both themes, and a student who types `#ef4444` would make the accent
identical to the Homework chip. A bounded set is the only form that keeps that
rule enforceable. Keeping the name-to-colour mapping in the stylesheet also
means a palette change, or a later move to `oklch()`, is a CSS edit rather than
a data migration.

Which accents to offer is open decision 4. Every candidate must clear the
distance-15 rule against all eight category colours in both themes before it is
added, which rules out plain blue, red, violet, green, pink, orange, indigo and
mid grey, since those are the categories.

### 3.3 Accent on category chips

```python
accent_chips: bool = Field(default=False, exclude_if=lambda value: value is False)
```

`False` keeps the per-category colours the app shows today, so the excluded
default means an old client never sees the key and nothing moves under it.

### 3.4 Motion level

```python
motion: Literal["off", "normal", "extra"] = Field(
    default="normal", exclude_if=lambda value: value == "normal"
)
```

These are exactly the three values `frontend/motion.js` already stores on the
device and writes to `<html data-motion>`, so a device value lifts onto the
account with no translation step. What happens to a level already stored on a
device when the account gains this field is open decision 5.

## 4. On a phone

The phone menu offers the pack and motion only.
Those two set the whole look, and the screen is small, so the Customize submenu must not take over the screen.

## 5. Contest cap

Ships for the contest:

- the five packs
- the accent colour control, with its optional chip toggle
- Motion Off, Normal and Extra

Waits until after the contest:

- a full per-surface colour picker
- anything beyond the three controls the Customize submenu already has
## Out of scope

- A full per-surface colour picker. This contract ships one accent colour; panels, text, borders, and
  backgrounds keep whatever the chosen pack defines for them.
- Blur sliders or any other way to tune frosted effects. Blur strength stays fixed inside each pack.
- Per-widget animation curves or timings. Motion is a single account-level setting applied everywhere.
- Any change to the solver or to week storage. This contract touches preferences and presentation only.
- Renaming, reordering, or adding packs beyond the five named in this contract.
- Any edit to spec.md before the owner approves this contract.

## Verification

### Backend (pytest against FastAPI)

- Rule: an old client that omits all four new fields still gets a valid response. Test: round-trip a
  preferences payload with no pack, no accent, no accent-on-chips flag, and no motion level, and
  assert it validates and the reply omits those keys, since unset optional fields are excluded.
- Rule: unknown keys stay rejected. Test: post preferences with a made-up key and assert FastAPI
  returns 422, because the model forbids extra keys.
- Rule: only an accent from the agreed set is accepted. Test: put a value outside the set and
  assert 422. The backend checks membership; proving the set itself is readable is a frontend job,
  below, because the colours live in the stylesheet and not in the model.
- Rule: the four new fields stay optional on the wire. Test: fetch preferences for a fresh account
  and assert the response JSON contains none of the four keys.

### Frontend (Node test files driving a fake DOM)

- Rule: nothing animates `backdrop-filter`, and no frosted panel is animated. Test: the stylesheet
  static tests keep passing unchanged: no rule animates or transitions `backdrop-filter` (the cause
  of the Windows flicker), no rule uses the `all` shorthand, keyframes move only opacity and
  transform, every animation sits inside `@media (prefers-reduced-motion: no-preference)`, and every
  animated selector is gated on Motion not being Off.
- Rule: Motion Off behaves exactly like the system reduced-motion setting. Test: in the fake DOM,
  set Motion to Off and simulate `prefers-reduced-motion: reduce`, then assert the same set of
  elements ends up static in both cases.
- Rule: Normal and Extra actually animate, and Extra goes further than Normal. Test: fake DOM
  checks that animated selectors activate at each level and stay silent when Motion is Off.
- Rule: every accent on offer stays clearly apart from every category colour. Test: extend the
  existing check in `frontend/tests/theme-tokens.test.mjs`, which today measures the single
  `--accent` token at a distance of at least 15 from all eight category colours in both themes, so
  that it walks the whole accent set instead. This is what makes a bounded set enforceable and a
  free hex string not.
- Rule: the phone menu shows only the pack and motion. Test: at phone width, assert exactly the
  pack picker and the motion control render, and the Customize submenu with its three controls
  stays collapsed until the user opens it on a wider screen.
- Rule: picking a pack applies everything it owns in one tap. Test: select each pack in the fake
  DOM and assert the background, the chrome, the accent, and the default motion level change
  together, and that any Customize choice made afterwards still wins.

## Open decisions for the owner

1. Are "Light frost" and "Dark frost" new token sets, or reworked renames of Slate and Nocturne?
   Recommendation: new token sets. The owner's own list names Light frost, Dark frost, Nocturne and
   Slate as four separate packs, so treating two of them as aliases of the other two would leave
   the menu with two names for one look.
2. Does the pack replace the existing theme field or sit beside it? Recommendation: add pack beside
   theme and let pack win when set, planning to retire theme in a later contract, because removing
   theme now would make old clients that still send it fail validation.
3. What happens to a motion level already stored on a device when the account gains the field?
   Recommendation: seed the account field once from the device value on first sync, then let the
   account value win while signed in. Keep writing the device copy: the sign-in screen has no
   account to read from, so it is the only level available before a student signs in.
4. Which accents are on offer? Recommendation: decide the list against the distance-15 rule before
   any of it is built. Under the bounded set in section 3.2 nothing can be too close at runtime,
   because a value outside the set is already a 422 and the set itself is proved readable by the
   frontend test. If the owner prefers a free hex field instead, that guarantee is lost and the
   check has to move to request time.
