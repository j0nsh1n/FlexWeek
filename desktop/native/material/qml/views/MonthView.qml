import QtQuick

Item {
    id: root
    objectName: "materialMonth"
    property var bridge

    Text {
        objectName: "screenTitle"
        anchors.centerIn: parent
        text: "Month"
        color: bridge && bridge.theme ? bridge.theme.onSurface : "#1a1c20"
        font.family: "Roboto Flex"
        font.pixelSize: 22
        font.weight: 500
    }
}
