import QtQuick
import components 1.0

// A title, a helper line and one button, for something to do rather than something to set (a test play).
SettingsRow {
    id: row
    property string key: ""
    property string buttonText: ""
    signal activated()
    objectName: "row_" + key

    Button {
        objectName: row.key
        theme: row.theme
        density: row.density
        reduceMotion: row.reduceMotion
        highContrast: row.highContrast
        kind: "tonal"
        text: row.buttonText
        accessName: row.buttonText
        onClicked: row.activated()
    }
}
