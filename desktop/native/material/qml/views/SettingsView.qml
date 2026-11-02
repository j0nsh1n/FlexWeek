import QtQuick
import components 1.0

Item {
    id: root
    objectName: "materialSettings"
    property var bridge

    Column {
        anchors.centerIn: parent
        spacing: 16
        width: 360

        Text {
            objectName: "screenTitle"
            text: "Settings"
            color: bridge && bridge.theme ? bridge.theme.onSurface : "#1a1c20"
            font.family: "Roboto Flex"
            font.pixelSize: 22
            font.weight: 500
        }

        Button {
            objectName: "useWidgets"
            text: "Widgets styles"
            theme: bridge ? bridge.theme : null
            density: bridge ? bridge.density : "comfortable"
            reduceMotion: bridge ? bridge.reduceMotion : false
            highContrast: bridge ? bridge.highContrast : false
            accessName: "Widgets styles"
            onClicked: bridge.useWidgets()
        }
    }
}
