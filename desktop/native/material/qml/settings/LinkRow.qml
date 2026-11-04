import QtQuick
import components 1.0

// A row that does something when pressed, with a chevron or a short value on the right.
SettingsRow {
    id: row
    property string key: ""
    property string trailing: "chevron"
    interactive: true
    objectName: "row_" + key
    accessName: title
    theme: Ui.theme

    M3Icon {
        visible: row.trailing === "chevron"
        name: "chevron_right"
        color: Ui.theme.onSurfaceVariant || "#44474e"
    }
}
