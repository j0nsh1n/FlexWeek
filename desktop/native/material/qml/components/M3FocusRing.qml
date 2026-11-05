import QtQuick

Rectangle {
    id: focusRing
    objectName: "focusRing"
    property Item target: parent
    property bool extra: true
    property bool shown: extra && shouldShow(target)
    property color ring: "transparent"
    property int ringRadius: 0
    // Item.focusReason is documented on Qt 6.8+ but is unset here (PySide 6.11.2),
    // so pointer vs keyboard is tracked from the press that caused focus.
    property bool hideForPointer: false

    function shouldShow(item) {
        if (!item)
            return false
        return item.activeFocus && !hideForPointer
    }

    PointHandler {
        id: pointerWatch
        acceptedButtons: Qt.LeftButton
        grabPermissions: PointerHandler.TakeOverForbidden
        onActiveChanged: {
            if (active)
                focusRing.hideForPointer = true
        }
    }

    Connections {
        target: focusRing.target
        function onActiveFocusChanged() {
            if (!focusRing.target || !focusRing.target.activeFocus)
                focusRing.hideForPointer = false
        }
    }

    visible: shown
    color: "transparent"
    border.width: 2
    border.color: ring
    radius: ringRadius
}
