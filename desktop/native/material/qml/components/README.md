# Material 3 components

Screens import `components 1.0` after `engine.addImportPath` of `desktop/native/material/qml`. Every public control takes the same three inputs. Pass one theme object through; do not read app data inside a control.

## Theme object

`property var theme`. Keys are camelCase Material role names. A missing key falls back to Blue light. The bridge should pass every key it has.

`primary`, `onPrimary`, `primaryContainer`, `onPrimaryContainer`, `secondary`, `onSecondary`, `secondaryContainer`, `onSecondaryContainer`, `tertiary`, `onTertiary`, `tertiaryContainer`, `onTertiaryContainer`, `error`, `onError`, `errorContainer`, `onErrorContainer`, `surface`, `onSurface`, `onSurfaceVariant`, `surfaceContainerLowest`, `surfaceContainerLow`, `surfaceContainer`, `surfaceContainerHigh`, `surfaceContainerHighest`, `surfaceVariant`, `outline`, `outlineVariant`, `inverseSurface`, `inverseOnSurface`, `inversePrimary`.

Values are `#rrggbb` strings. Disabled controls mix `onSurface` at 12% for the fill and 38% for the ink. A text button's disabled fill stays clear. The dialog scrim is `rgba(0,0,0,0.32)` and is not a token.

## Other inputs

- `density`: `"comfortable"` (default) or `"compact"`. Compact changes settings-row vertical padding from 16 to 10. Nothing else shrinks.
- `reduceMotion`: when true, colour and position animations run at duration 0. The easing otherwise is the emphasized curve `cubic-bezier(.2, 0, 0, 1)` (200 ms colour, 300 ms the switch thumb).
- `highContrast`: when true, strokes are 1.5 px and settings dividers use `outline`. The theme object has no contrast flag. Pair this with a high-contrast scheme such as Blue light high.

## What the shell registers

Font files, the same Inter faces the other styles use:

- `desktop/assets/fonts/Inter-Regular.ttf` (weight 400)
- `desktop/assets/fonts/Inter-Medium.ttf` (weight 500)
- `desktop/assets/fonts/Inter-SemiBold.ttf` (weight 600)
- `desktop/assets/fonts/LICENSE.txt` (Inter's OFL)

Family name is `Inter`. Register each file with `QFontDatabase.addApplicationFont`, the same call `load_fonts` uses. `M3Font` also loads the three files for text inside this module.

Icons are the rounded Material Symbols, weight 400, copied into `desktop/native/material/qml/icons/`. The Apache-2.0 notice is `icons/LICENSE`. Names in use: `add`, `arrow_back`, `calendar_month`, `calendar_view_day`, `calendar_view_week`, `check`, `chevron_left`, `chevron_right`, `close`, `edit_note`, `more_vert`, `pause`, `play_arrow`, `redo`, `schedule`, `school`, `settings`, `task_alt`, `undo`, `warning`, `wb_sunny`. `warning` (the status chip for cutting it close) is drawn for FlexWeek on the same 960 grid; it is not a Material Symbols file.

## Public types

`NavRail` (width 80, surface container low), `NavDestination` (pill 56 by 32), `NavBar` (height 80, surface container), `Fab` (56, radius 16, primary container), `ExtendedFab`, `Button` (`kind`: `filled`, `tonal`, `outlined`, `text`), `IconButton`, `SegmentedButton` (height 40, radius 20, 18 px check), `Switch` (52 by 32; thumb 16 off, 24 on), `PresetSwatch` (disc 48, badge 22), `SettingsGroup` (radius 16), `SettingsRow`, `ListRow` (optional `fill`, `ink`, `trail`), `Tag` (`kind`: `plain`, `tight`, `plenty`, `cutting`), `EventBlock` (`category`: `school`, `sports`, `study`, `homework`), `OutlinedField`, `Dialog` (radius 28, width 440), `BottomSheet`, `Menu` (width 260), `Snackbar` (height 48; the parent anchors it 24 px from the bottom, 96 px on a phone), `MiniMonth`.

`Gallery` draws every control in every state. Set `scheme` to `light`, `dark`, or `high`.

## Not part of the screen API

`M3Palette`, `M3Font`, `M3Icon`, `M3StateLayer`, and `M3FocusRing` are shared inside the module. `M3Palette` keeps the on-colours under names such as `inkSurface`, because a QML name that starts with `on` is a signal handler. Callers still pass `onSurface` on the theme object. Category colours live on `EventBlock`, not on the theme. Quadrant colours on `PresetSwatch` are `quadrantPrimary`, `quadrantTertiary`, `quadrantSecondary`, and `quadrantPrimaryContainer` (the preset's primary, tertiary, secondary container, and primary container).

Keyboard: Space, Return, and Enter activate. Left and Right move a segmented button. Up and Down move a menu. Escape closes a dialog, a sheet, and a menu. Each interactive control has `objectName`, `Accessible.name`, and a role, plus a 2 px focus ring in `primary` with a 2 px gap.
