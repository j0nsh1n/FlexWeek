# Contract: appearance packs, accent and motion

Status: approved 2026-09-17 by the owner. Claude owns the browser/desktop
frontend. Grok owns the preference fields on `GET`/`PUT /api/preferences`.
Both clients continue to use the same HTML, CSS and JavaScript frontend.

This contract is based on `feat/0-11-seamless` at `dca7fd3`, which already
shipped the motion levels below as a device-only setting. The account fields
and the pack UI landed with the 2026-09-17 approval.

Sections 1–5 were drafted by GLM through OpenCode, then checked against source.
The owner settled the open decisions on 2026-09-17. Those answers are written
into the sections they affect, not listed as questions.

## Goal

A student picks one of five theme packs: System, Light frost, Dark frost,
Nocturne or Slate. A pack sets the background, the chrome, the accent and the
default motion level together, so the whole look is one choice.
When it is built, a student can also open the Customize submenu and set their
own accent, optionally apply that accent to category chips, and set Motion to
Off, Normal or Extra.
Their accent and motion choices override the pack defaults. Motion Off behaves
exactly like the device's reduced-motion setting.

## 1. Theme packs

The app today has a single theme choice with three values.
"system" follows the device's light or dark setting, "slate" is shown to
students as Light, and "nocturne" is shown as Dark.
The stylesheet reads `<html data-theme>` and only ever sees "slate" or
"nocturne". Both are already frosted looks built from backdrop-filter, with a
solid fallback when blur is unavailable.

The five packs are five looks, not three looks with extra names.

- **System** is the existing "system" value. Its background and chrome follow
  the device, resolving to the slate or nocturne stylesheet until Light frost
  and Dark frost have their own maps; its accent and default motion are its own.
- **Nocturne** and **Slate** are the existing "nocturne" and "slate" values,
  presented under their own names, and they keep shipping.
- **Light frost** and **Dark frost** are new token sets. Each needs its own
  background, chrome, accent and motion default. The stylesheet needs a value
  it understands for them, because today it only ever sees "slate" or
  "nocturne". Aliasing them to Slate and Nocturne would put two menu names on
  one look.

What a pack sets:

- the background
- the chrome
- the accent
- the default motion level

What a pack does not touch:

- a student's own accent and motion choices, which override the pack defaults
- the solid fallback that shows when blur is unavailable
- the animation of anything frosted, because recompositing backdrop-filter
  flickers on Windows

`theme` stays on the wire. It is required today, with no default, and old
clients still send it. The pack sits beside it.

- When `theme_pack` is omitted or `system`, `theme` behaves as it does today:
  `system`, `slate` or `nocturne`.
- When `theme_pack` is `light-frost` or `slate`, stored `theme` must be `slate`.
- When `theme_pack` is `dark-frost` or `nocturne`, stored `theme` must be
  `nocturne`.

The client keeps those in step when the student picks a pack. A pair that
breaks the axis is a 422. Pack is what the new menu shows. `theme` is what
0.10 clients still round-trip.

## 2. The Customize submenu

The submenu is collapsed by default. It holds exactly three controls, no more.

- **Accent colour.** Sets the accent the app uses, overriding the pack default.
  It does not recolour any surface on its own, and it never touches the
  background or the chrome.
- **Use the accent for category chips.** An optional toggle. On, category chips
  take the accent colour. Off, which is the default, chips keep their normal
  colours. It changes nothing else.
- **Motion.** Off, Normal or Extra, written to `<html data-motion>`. This
  contract stores it on the account (section 3.4). A copy also stays on the
  device, because the sign-in screen has no account to read from.
  - Off must behave exactly like the system prefers-reduced-motion setting.
    Nothing moves.
  - Normal fades the calendar between Week, Day and Month.
  - Extra adds a short rise on the view change and pops in work a plan just
    placed.
  - There are no blur sliders and no per-widget curves, and nothing frosted is
    animated, because recompositing backdrop-filter flickers on Windows.

On a phone the menu offers the pack and motion only. Customize is not shown at
phone width. It is not a collapsed panel the student can open there.

## 3. New preference fields

Every field follows the pattern the model already uses: a default plus an
`exclude_if` that drops the field from the response while it holds that
default. An old client that never sends the key still validates, and never
meets it on the way back. `extra="forbid"` is unchanged, so a misspelled key is
still a 422. The four fields are stored in `comfort_json` with the Stage 5
comfort keys. `theme` stays its own column.

### 3.1 Theme pack

```python
theme_pack: Literal["system", "light-frost", "dark-frost", "nocturne", "slate"] = Field(
    default="system", exclude_if=lambda value: value == "system"
)
```

The bound is membership in the Literal. The field sits beside `theme`. Pack
selects the look. `theme` keeps owning the light/dark/system axis that
`<html data-theme>` already reads, with the pairing in section 1.

The default is excluded from responses, so an old client never receives a
`theme_pack` key and keeps rendering exactly as it does today.

### 3.2 Accent colour

```python
accent: Literal["default", "sky", "gold", "sea", "sand"] = Field(
    default="default", exclude_if=lambda value: value == "default"
)
```

A bounded set of named accents, not a free hex string. `default` means the
pack's own accent. The other four names are the contest set. Their colours live
in the stylesheet, one value per theme, and each must keep a colour distance of
at least 15 from all eight category colours in both themes
(`frontend/tests/theme-tokens.test.mjs`). That rule already fails plain blue,
red, violet, green, pink, orange, indigo and mid grey, because those are the
categories.

A regex only proves a string is hex-shaped. A student who typed `#ef4444`
would make the accent identical to the Homework chip. Keeping the name-to-colour
mapping in the stylesheet also means a palette change, or a later move to
`oklch()`, is a CSS edit rather than a data migration.

### 3.3 Accent on category chips

```python
accent_chips: bool = Field(default=False, exclude_if=lambda value: value is False)
```

`False` keeps the per-category colours the app shows today, so the excluded
default means an old client never sees the key and nothing moves under it.

### 3.4 Motion level

```python
motion: Literal["off", "normal", "extra"] | None = Field(
    default=None, exclude_if=lambda value: value is None
)
```

These are exactly the three values `frontend/motion.js` already stores on the
device and writes to `<html data-motion>`. `None` (omitted) means the account
has never stored a level. That is the only way to tell "never set" from an
explicit Normal. `exclude_if` drops only `None`. Once a client writes `off`,
`normal` or `extra`, GET returns that key, including `"motion": "normal"`.

On first sign-in after this field exists, if GET omits `motion`, the client
writes the device value once, including Normal. After that the account value
wins while signed in. The device copy is still written on every change, because
the sign-in screen has no account to read from. A second device does not seed
again, because GET now carries the key.

`prefers-reduced-motion: reduce` still wins over any stored level.

## 4. On a phone

The phone menu offers the pack and motion only.
Those two set the whole look, and the screen is small, so Customize is hidden
at phone width.

## 5. Contest cap

Ships for the contest:

- the five packs
- the accent colour control, with its optional chip toggle, using the five
  names in section 3.2
- Motion Off, Normal and Extra

Waits until after the contest:

- a full per-surface colour picker
- anything beyond the three controls the Customize submenu already has
- more named accents than the five in section 3.2

## Out of scope

- A full per-surface colour picker. This contract ships one accent colour.
  Panels, text, borders, and backgrounds keep whatever the chosen pack defines
  for them.
- Blur sliders or any other way to tune frosted effects. Blur strength stays
  fixed inside each pack.
- Per-widget animation curves or timings. Motion is a single account-level
  setting applied everywhere, plus the device copy for signed-out screens.
- Any change to the solver or to week storage. This contract touches
  preferences and presentation only.
- Renaming, reordering, or adding packs beyond the five named in this contract.
- Replacing or removing the `theme` field in this release.

## Verification

### Backend (pytest against FastAPI)

- Rule: an old client that omits all four new fields still gets a valid
  response. Test: round-trip a preferences payload with no pack, no accent, no
  accent-on-chips flag, and no motion level, and assert it validates and the
  reply omits those keys.
- Rule: unknown keys stay rejected. Test: post preferences with a made-up key
  and assert FastAPI returns 422, because the model forbids extra keys.
- Rule: only an accent from the agreed set is accepted. Test: put a value
  outside the set and assert 422. The backend checks membership. Proving the
  set itself is readable is a frontend job, below, because the colours live in
  the stylesheet and not in the model.
- Rule: the four new fields stay optional on the wire. Test: fetch preferences
  for a fresh account and assert the response JSON contains none of the four
  keys.
- Rule: an explicit Normal is not treated as unset. Test: put `"motion":
  "normal"` and assert GET returns that key and value, so a second device
  cannot seed over it.
- Rule: a set pack keeps `theme` on its light or dark axis. Test: put
  `theme_pack` `dark-frost` with `theme` `slate` and assert 422. Put
  `dark-frost` with `nocturne` and assert 200.

### Frontend (Node test files driving a fake DOM)

- Rule: nothing animates `backdrop-filter`, and no frosted panel is animated.
  Test: the stylesheet static tests keep passing unchanged: no rule animates or
  transitions `backdrop-filter` (the cause of the Windows flicker), no rule
  uses the `all` shorthand, keyframes move only opacity and transform, every
  animation sits inside `@media (prefers-reduced-motion: no-preference)`, and
  every animated selector is gated on Motion not being Off.
- Rule: Motion Off behaves exactly like the system reduced-motion setting.
  Test: in the fake DOM, set Motion to Off and simulate
  `prefers-reduced-motion: reduce`, then assert the same set of elements ends
  up static in both cases.
- Rule: Normal and Extra actually animate, and Extra goes further than Normal.
  Test: fake DOM checks that animated selectors activate at each level and stay
  silent when Motion is Off.
- Rule: every accent on offer stays clearly apart from every category colour.
  Test: extend the existing check in `frontend/tests/theme-tokens.test.mjs`,
  which today measures the single `--accent` token at a distance of at least 15
  from all eight category colours in both themes, so that it walks the whole
  accent set instead.
- Rule: the phone menu shows only the pack and motion. Test: at phone width,
  assert exactly the pack picker and the motion control render, and Customize
  with its three controls is not in the layout.
- Rule: picking a pack applies everything it owns in one tap. Test: select each
  pack in the fake DOM and assert the background, the chrome, the accent, and
  the default motion level change together, and that any Customize choice made
  afterwards still wins.

The backend tests land with the preference fields. The frontend tests land with
the pack UI.
