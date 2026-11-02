import QtQuick
import QtQuick.Layouts
import components 1.0

// Start from a style: Material 3 first, then the standard styles. Next keeps the pick.
Column {
    id: page
    objectName: "setupStylePage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 16

    GridLayout {
        width: parent.width
        columns: page.phone || page.width < 620 ? 1 : 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.stylesModel : null
            ChoiceCard {
                required property var row
                Layout.fillWidth: true
                objectName: "setupStyle-" + row.key
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: row.name
                note: row.note
                selected: row.selected
                onChosen: page.bridge.chooseStyle(row.key)
            }
        }
    }
    Button {
        objectName: "setupOwnLook"
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        kind: "outlined"
        text: bridge ? bridge.ownLookLabel : ""
        onClicked: page.bridge.chooseOwnLook()
    }
}
