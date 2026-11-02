import QtQuick

Rectangle {
    property bool shown: false
    property color ring: "#425e91"
    property int ringRadius: 0
    visible: shown
    color: "transparent"
    border.width: 2
    border.color: ring
    radius: ringRadius
}
