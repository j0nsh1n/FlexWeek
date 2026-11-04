import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string message: "Placed 2 of 2"
    property string actionText: "UNDO"
    property string accessName: ""
    signal actionClicked()
    signal pauseRequested()
    signal resumeRequested()

    HoverHandler { id: toastHover }
    readonly property bool pointerHovered: toastHover.hovered
    readonly property bool keyboardFocused: root.activeFocus || (action && action.activeFocus)
    // Visibility is part of the hold: a notice shown again under a pointer that never moved
    // still sends a pause, and hiding one always sends a resume.
    readonly property bool held: visible && (pointerHovered || keyboardFocused)

    onHeldChanged: {
        if (held)
            root.pauseRequested()
        else
            root.resumeRequested()
    }

    onVisibleChanged: {
        if (!visible && activeFocus && parent)
            parent.forceActiveFocus()
    }

    onActionTextChanged: {
        if (actionText === "" && activeFocus && parent)
            parent.forceActiveFocus()
    }

    implicitHeight: 48
    height: 48
    implicitWidth: Math.max(240, messageText.implicitWidth + action.width + 48)
    width: implicitWidth

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 4
        color: palette.inverseSurface
    }
    Text {
        id: messageText
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        text: root.message
        color: palette.inverseOnSurface
        font.family: M3Font.family
        font.pixelSize: 14
        font.weight: 400
    }
    Item {
        id: action
        visible: root.actionText !== ""
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        width: actionRow.implicitWidth + 16
        height: 36
        Row {
            id: actionRow
            anchors.centerIn: parent
            spacing: 6
            Text {
                id: actionTextItem
                text: root.actionText
                color: palette.inversePrimary
                font.family: M3Font.family
                font.pixelSize: 14
                font.weight: 500
            }
            Text {
                id: shortcutHintItem
                objectName: "shortcutHint"
                visible: root.actionText === "UNDO" || root.actionText.indexOf("Undo") !== -1
                text: "Ctrl+Z"
                color: palette.inversePrimary
                opacity: 0.85
                font.family: M3Font.family
                font.pixelSize: 11
                font.weight: 500
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        M3StateLayer {
            anchors.fill: parent
            radius: 18
            color: palette.inversePrimary
            hovered: hover.hovered
            down: tap.pressed || root.keyDown
            reduceMotion: root.reduceMotion
        }
        M3FocusRing {
            anchors.fill: parent
            anchors.margins: -2
            shown: root.activeFocus
            ring: palette.inversePrimary
            ringRadius: 20
        }
        HoverHandler { id: hover }
        TapHandler { id: tap; onTapped: root.actionClicked() }
    }

    property bool keyDown: false
    activeFocusOnTab: actionText !== ""
    Accessible.role: actionText !== "" ? Accessible.Button : Accessible.StaticText
    Accessible.name: (accessName !== "" ? accessName : message) + (actionText !== "" ? ", " + actionText : "") + (shortcutHintItem.visible ? " (Ctrl+Z)" : "")
    Accessible.onPressAction: if (actionText !== "") root.actionClicked()
    Keys.enabled: actionText !== ""
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown)
                root.actionClicked()
            root.keyDown = false
            event.accepted = true
        }
    }
}
