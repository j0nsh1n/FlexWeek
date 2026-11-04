import QtQuick
import QtQuick.Layouts
import components 1.0

// How the week is laid out, for a student who builds their own look.
Column {
    id: page
    objectName: "setupLookPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 12

    GridLayout {
        width: parent.width
        columns: page.phone || page.width < 620 ? 1 : 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.mainsModel : null
            ChoiceCard {
                required property var row
                Layout.fillWidth: true
                objectName: "setupMain-" + row.id
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: row.label
                note: row.note
                selected: row.selected
                onChosen: page.bridge.chooseMain(row.id)
            }
        }
    }
}
