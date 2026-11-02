import QtQuick
import QtQuick.Controls.impl

Item {
    id: icon
    property string name: "check"
    property alias color: image.color
    width: 24
    height: 24
    IconImage {
        id: image
        anchors.fill: parent
        source: icon.name === "" ? "" : Qt.resolvedUrl("../icons/" + icon.name + ".svg")
        sourceSize.width: width
        sourceSize.height: height
        color: "#1a1c20"
    }
}
