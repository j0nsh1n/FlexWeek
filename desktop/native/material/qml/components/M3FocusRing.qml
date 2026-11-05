import QtQuick

// The shared keyboard focus ring: 2 px in the focus colour with a 2 px gap. It shows on the focused
// item only while the last input was a key, so a click never leaves a ring behind.
Rectangle {
    id: focusRing
    objectName: "focusRing"
    property Item target: parent
    property bool extra: true
    property bool shown: extra && !!target && target.activeFocus && FocusVisible.keyboard
    property color ring: "transparent"
    property int ringRadius: 0

    visible: shown
    color: "transparent"
    border.width: 2
    border.color: ring
    radius: ringRadius
}
