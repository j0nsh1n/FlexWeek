import QtQuick
import components 1.0

// A title, a helper line and a switch. `key` names the switch for tests and the accessibility tree.
SettingsRow {
    id: row
    property string key: ""
    property bool isOn: false
    signal flipped(bool value)
    objectName: "row_" + key

    Switch {
        id: sw
        objectName: row.key
        theme: row.theme
        density: row.density
        reduceMotion: row.reduceMotion
        highContrast: row.highContrast
        checked: row.isOn
        accessName: row.title
        onToggled: (on) => row.flipped(on)
    }
    onIsOnChanged: sw.checked = isOn
    // A failed save leaves isOn alone, so the switch is put back with the saved state.
    Connections {
        target: Ui.settings
        function onChanged() { sw.checked = row.isOn }
    }
}
