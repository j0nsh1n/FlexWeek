import QtQuick

Item {
    id: root
    objectName: "materialMyDay"
    property var bridge

    Text {
        objectName: "screenTitle"
        anchors.centerIn: parent
        text: "My day"
        color: bridge && bridge.theme ? bridge.theme.onSurface : "#1a1c20"
        font.family: "Roboto Flex"
        font.pixelSize: 22
        font.weight: 500
    }
}
