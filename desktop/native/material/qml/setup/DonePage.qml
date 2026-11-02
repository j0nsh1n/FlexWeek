import QtQuick
import QtQuick.Layouts
import components 1.0

// What was chosen, with a Change button beside each answer.
Column {
    id: page
    objectName: "setupDonePage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 0

    SettingsGroup {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        Repeater {
            model: bridge ? bridge.summaryModel : null
            SettingsRow {
                id: line
                required property var row
                required property int index
                width: page.width
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: row.name
                subtitle: row.value
                showDivider: index < 4
                Button {
                    objectName: "setupChange" + line.index
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    kind: "text"
                    text: "Change"
                    accessName: "Change " + line.row.name.toLowerCase()
                    onClicked: page.bridge.setupJump(page.bridge.stepFor(line.index))
                }
            }
        }
    }
}
