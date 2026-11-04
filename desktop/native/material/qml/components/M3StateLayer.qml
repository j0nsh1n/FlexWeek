import QtQuick

Rectangle {
    id: layer
    property bool hovered: false
    property bool down: false
    property bool reduceMotion: false
    radius: 0
    opacity: down ? 0.12 : hovered ? 0.08 : 0
    Behavior on opacity {
        NumberAnimation {
            duration: layer.reduceMotion ? 0 : 200
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }
}
