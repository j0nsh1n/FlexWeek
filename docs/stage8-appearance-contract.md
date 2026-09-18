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

## Amendment A (proposed 2026-09-17): presets and look knobs

Status: proposed. Needs owner approval before any of the fields below reach
spec.md or the preferences model. Until then everything in this amendment is
device-only: stored in the browser under `flexweek-look`, applied from
`frontend/look.js` in `<head>`, and never sent to `/api/preferences`. A test
asserts that.

The owner asked for more control over the interface and for presets that look
drastically different from the frost family rather than palette swaps of it.
Both come from one idea: a preset is a bundle of knob values plus a palette, and
Customize edits the same knobs. Adding a preset is then a token map and seven
values, and adding a knob is one attribute, one control, one field, one test.

### A1. Knobs

A knob is one attribute on `<html>` that the stylesheet reads. Each moves one
kind of thing and nothing else; a static test enforces that, so a knob can
never smuggle in a colour or an animation. Accent and motion are already knobs
on the account (sections 3.2 and 3.4) and stay as they are.

| Knob | Values | Default | What it moves |
| --- | --- | --- | --- |
| surface | frost, flat | frost | frosted panels, or solid ones with no blur |
| corners | round, sharp, pill | round | the three radius tokens |
| depth | soft, flat, hard | soft | diffuse shadows, none, or hard offset ones |
| font | sans, mono, serif | sans | Figtree, the system monospace, the system serif |
| blocks | filled, outlined, edge | filled | where a category's colour lands on a calendar block |
| density | comfortable, compact | comfortable | hour height and spacing |
| text | small, normal, large | normal | the base size; rem scales with it |

The font and text knobs use system faces and sizes only. No new font files
ship with them.

### A2. Presets

A preset names a palette, which is a complete token map audited by the same
tests as a pack (same tokens, AA text, accent distance), and sets every knob
the student has not moved by hand. Customize then edits from there.

Built as device-only presets, audited like packs (same tokens, AA text, accent
distance). Nothing here is saved on the account until Amendment A is approved.

Look is one menu: the five account packs, then Terminal, Poster, Ink, High
contrast, Paper and Pastel on this device. Pack default is choosing the pack itself.

- **Terminal**. True black, phosphor text, amber accent; flat surface, sharp
  corners, no shadows, monospace, outlined blocks, compact.
- **Poster**. Yellow field, navy ink, dark red accent; flat surface, sharp
  corners, hard offset shadows, filled blocks, compact, large type.
- **Ink**. Near-monochrome; category colour only as a thin edge; hairlines
  instead of fills; no shadows; serif type. Light packs get the paper map,
  dark packs the charcoal map.
- **High contrast**. Black, white and yellow; thick borders; outlined blocks;
  large text. It turns on only from this menu, never from the operating
  system's contrast setting, in case that signal is wrong.
  `prefers-contrast: more` still only turns frosted panels solid.
- **Paper**. A planner notebook: warm cream, brown ink, a sepia accent, serif
  type; flat surface, round corners, soft shadows, filled blocks. It is warmer
  than Ink's light sheet on purpose, and rounded where Ink is sharp.
- **Pastel**. Pink and lavender surfaces, pill corners, soft shadows and raised
  panels; sans type, filled blocks. The softness lives in the surfaces. The
  accent is a deep orchid, because a pale lavender cannot pass as text at 4.5
  to 1 and would sit too near the violet and indigo category colours.

Paper and Pastel are the two soft looks: every other preset is flat and sharp.
Both are light whatever pack sits underneath, as Poster is, so a chosen accent
takes its light-axis colour even over a dark pack. Pill corners are capped at
half a rem on calendar blocks, so a tall block keeps its title. Claude built
both on 2026-09-18, in both clients, under the same audits as the others.

Relationship to packs: a pack is a palette with the knobs at their defaults; a
preset is a palette with its own knob values. Once Amendment A is approved they
join `theme_pack` with an axis for the existing validator (Terminal is dark).

### A3. Proposed preference fields

```python
look_surface: Literal["frost", "flat"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_corners: Literal["round", "sharp", "pill"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_depth: Literal["soft", "flat", "hard"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_font: Literal["sans", "mono", "serif"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_blocks: Literal["filled", "outlined", "edge"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_density: Literal["comfortable", "compact"] | None = Field(default=None, exclude_if=lambda value: value is None)
look_text: Literal["small", "normal", "large"] | None = Field(default=None, exclude_if=lambda value: value is None)
```

`None` means "whatever the pack or preset says", so an old client that omits
them keeps the look it has, and an explicit value is a deliberate override.
Choosing a look keeps knobs the student set by hand; only those overrides are
stored, and the rest stay `None`. `extra="forbid"` is unchanged.

### A4. On a phone

Look, Text size and Motion sit up front. The other knobs stay inside
Customize, which is hidden on phones as today.

### A5. Verification

Static, in `frontend/tests/theme-tokens.test.mjs`: each knob rule moves only
the properties it names; the flat surface clears `backdrop-filter` on exactly
the frosted panels; the Terminal, Poster, Ink and High contrast maps pass the
same-tokens, readability and accent-distance audits; blocks take their colour
through `--block-color`.

Behaviour, in `frontend/tests/stage5_comfort.test.mjs`: the look and knobs
change nothing on the server and never enter the payload; a look fills in only
the knobs the student left alone; a hand-set knob stays when the look changes;
a stored look applies before the body paints; a bad stored value falls back to
the pack.

Backend, once approved: a round-trip with all seven omitted still validates and
returns none of them; a value outside a Literal is a 422; the pack-axis
validator still holds for every new preset.

### Owner answers 2026-09-18

1. Fold Preset into Look. One menu: packs, then the device presets.
2. High contrast turns on only from that menu. It must not follow
   `prefers-contrast: more`, in case the operating system reports it by
   mistake. Paper and Pastel stay for Claude.
3. A look acclimates to knobs set by hand. Choosing Terminal, Poster, Ink or
   High contrast keeps those overrides and fills in the rest.

## Amendment B — Native Qt client

Drafted 2026-09-18 against `feat/native-python`. The default desktop launcher
is Qt widgets (`python -m desktop.main`), not the HTML frontend named in the
Goal. Packs, knobs and presets still share one contract: the same ids, the
same knob values, and the same audited hex for the colours Qt can draw.
`desktop/native/look.py` is the native table. `frontend/look.js` and the token
maps in `frontend/styles.css` are the web table.
`desktop/tests/test_look.py` fails if those hex values drift.

What Qt cannot copy from CSS:

- `backdrop-filter`. Frost vs flat is a panel colour. Frost uses the solid
  panel token as a raised surface. Flat paints the panel and the field in the
  page colour.
- Drop shadows. Soft depth is a 1px hairline, flat is no border, hard is a
  heavy bottom and right edge in the strong hairline colour.
- Translucent hairlines. The web states them as `rgba`. Native mixes the tint
  over the panel and stores the solid.

Look stays on this device. Native writes `flexweek-look.json` under the Qt
app data folder. The web client still uses `localStorage` key `flexweek-look`.
Neither `PUT /api/preferences` payload includes look keys until Amendment A
is approved.

Ink is the only preset with two palettes. Light packs (Slate, Light frost, or
System on a light device) get the light map. Dark packs get the dark map.
Poster, Terminal and High contrast are one look on every pack.

Large text enlarges the More menu: web `#week-menu` items, and the native More
button's menu, so overflow actions stay tappable.

spec.md drift: the native launcher, the four device-only presets, and the
proposed `look_*` fields are not in spec.md. Do not edit spec.md until the
owner approves them.
