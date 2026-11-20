# Contract: appearance, accent and motion

Status: the account fields were approved on 2026-09-17. This copy describes the
current Material desktop interface and the existing API. The retired browser,
Widgets design and look-editor amendments are not current product contracts.

## Current desktop appearance

Material 3 is the only desktop interface. Its ordinary Look settings are the
colour preset, account accent, accent on category chips, animation level, mode,
contrast, density, font, text size, weekend visibility and clock. Advanced
settings holds the remaining layout and colour controls with a live preview.

The presets are Slate, Blue, Sea, Forest, Gold, Rose, Plum, High contrast,
Paper, Ink and Terminal. Slate is the default. High contrast is dark with a
fixed yellow accent, Paper is light, and Ink and Terminal are dark; these four
keep their own mode. Paper and Ink default to Serif, Terminal to Mono and sharp
corners, and High contrast to sharp corners. A student's own font and advanced
corner choice win over those defaults.

Mode is System, Light or Dark. Contrast is Standard or High. Density is
Comfortable or Compact. Font is Sans (Inter), Serif (Newsreader headings over
Inter) or Mono (JetBrains Mono). Text size is Small, Normal, Large or Larger.

Advanced settings has three tiers, stored as `material.lookTier` on this
computer:

- **Simple:** preset, mode, corner shape, block style, row size and text size.
- **More:** the Simple controls plus corner radius, hour row height, card
  padding, rail labels, text scale, motion speed, shadow, hour lines, today
  highlight, times, lengths and weekend visibility.
- **All:** the More controls plus the now-line and category colour codes and
  the readability check with Fix and Fix all.

Every tier edits the same draft. Done applies it and Back drops it. Changing
the tier never changes a value. The page starts on Simple, or All after a setup
that used the detailed controls when no tier was chosen yet. Show weekends is
an account preference and applies at once even from this draft page.

## Local look file

`flexweek-look.json` is in the app's data folder. Its `material` object holds:

- `preset`, `mode`, `contrast` and `density`;
- `shortcuts` for number keys and `letters` for letter keys;
- `advanced`, the advanced controls;
- optional `font`, `saved` looks and `lookTier`.

A missing or unknown basic value falls back to Slate, System, Standard contrast
and Comfortable density. A missing font means the preset's own. Number keys are
on and letter keys are off unless the file says otherwise. `store_material`
leaves the file's other top-level keys alone.

A saved Material look holds its name, basic choice and advanced controls. The
Advanced page exports and imports a JSON document of kind
`FlexWeek material look`, version 1. A document of another kind or version is
refused. Unknown or invalid values fall back to their defaults.

## Account preference fields

The existing fields remain on `GET` and `PUT /api/preferences`. Defaults are
omitted as their model declares, and `extra="forbid"` still rejects unknown
keys.

```python
accent: Literal["default", "sky", "gold", "sea", "sand"]
accent_chips: bool
motion: Literal["off", "normal", "extra", "reduce"] | None
```

`default` is shown as Same as preset. Sky, Gold, Sea and Sand replace the
preset's primary colours; High contrast always keeps its yellow. Accent on
category chips makes every category use the accent rather than its own colour.

Animations has four values:

| Student choice | Stored value | Behaviour |
|---|---|---|
| Off | `off` | Nothing animates. |
| Reduce | `reduce` | Short fades remain, but nothing travels. |
| Normal | `normal` | The ordinary durations and distances run. |
| More | `extra` | Durations are 2.5 times Normal and distances are four thirds of Normal. |

An omitted `motion` means the account has never chosen a level and Material uses
Normal. An explicit `"normal"` stays on the wire so another device cannot treat
it as unset. The Advanced page also lists a separate local Speed control.
Slower multiplies durations by 1.5, Faster by 0.6, and Off stops animation.
`desktop/native/motion_level.py` holds the level rules and
`desktop/native/material/bridge.py` passes their pace and reach to QML.

The older `theme` and `theme_pack` fields remain valid on the API for existing
clients. Material's own preset and mode are local; it does not read those two
fields. Their existing validation is unchanged:

```python
theme: Literal["system", "slate", "nocturne"]
theme_pack: Literal["system", "light-frost", "dark-frost", "nocturne", "slate"]
```

When `theme_pack` is `light-frost` or `slate`, stored `theme` must be `slate`.
When it is `dark-frost` or `nocturne`, stored `theme` must be `nocturne`. A pair
that breaks that axis is a 422. `NativeSession.save_preferences` keeps the axis
in step when a client writes `theme_pack`.

## Readability

The schemes in `desktop/native/material/tokens.json` provide the Material roles
for every preset, mode and contrast. High contrast also draws a solid 1.5 px
outline. Category fills and their ink are checked to read at 4.5:1 or better;
the now line check needs 3:1.

All's readability list reports only colours the student set that fail those
limits. Fix moves that colour's lightness to the nearest readable value. Fix all
applies the computed fix to each listed colour once.

## Verification

- Omitting accent, accent-on-chips and motion still validates and returns those
  keys omitted; an explicit Normal is returned.
- An unknown preference key, accent or motion level is a 422.
- A set `theme_pack` must keep `theme` on its light or dark axis.
- Every Material preset, mode and contrast has the colour roles QML reads.
- Changing Simple, More or All does not change any value, and the tier survives
  reopening Settings and restarting the app.
- A Material look export imports back with the same basic and advanced choices;
  another kind or version is refused.
- Readability checks catch a category below 4.5:1 and a now line below 3:1.
