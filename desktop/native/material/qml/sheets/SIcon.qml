import QtQuick
import QtQuick.Controls.impl

// A sheet icon. The shared Material symbols live in ../icons; the few this folder draws live in icons/.
Item {
    id: icon
    property string name: "check"
    property alias color: image.color
    readonly property var own: ["expand_more", "expand_less", "list", "repeat", "timer", "event_busy",
        "autorenew", "save", "help", "info", "logout", "delete", "link"]
    width: 24
    height: 24
    IconImage {
        id: image
        anchors.fill: parent
        source: icon.name === "" ? "" : Qt.resolvedUrl((icon.own.indexOf(icon.name) >= 0 ? "icons/" : "../icons/") + icon.name + ".svg")
        sourceSize.width: width
        sourceSize.height: height
        color: "#1a1c20"
    }
}
