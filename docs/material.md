# Material 3

Material 3 is a whole-window surface beside the Qt Widgets styles. The student chooses it the same way as a style, from Settings, and can swap back without restarting. Today's app stays the default. The saved choice is the top-level `surface` key in the look file: `widgets` or `material`. A file with no `surface`, or a value this build does not know, opens on the Widgets styles. `layout` is unchanged.

The shell is `desktop/native/material/qml/Main.qml`. It reads the week only through `MaterialBridge`, and the bridge only through `NativeSession`. While Material is the surface on screen, a refresh does not put the Widgets week back, and the Widgets prompts for unfinished work and the plan review are not consumed. The Material settings page in this slice is only the way back to the Widgets styles.

If the QML page fails to load, or the scene graph reports an error, FlexWeek shows the Widgets week, keeps the session, and leaves the saved choice as Material.

A frozen build includes `desktop/native/material/tokens.json` and `desktop/native/material/qml/` next to the executable, which is where `theme.py` looks when the files are not beside the source. `desktop/check_bundle.py` reports a bundle that is missing either file. CI still has to prove the packed app also contains Qt Quick Controls' Material module and opens Material without falling back. That Nuitka build is not run on a working machine.

The rig clicks a QML item by its `objectName` or its words. It walks the item's visual children, because a repeater row is not a `QObject` child and `Repeater.itemAt` returns nothing through PySide. Day, Month, and My day stay hidden unless `FLEXWEEK_MATERIAL_LATER=1`.
