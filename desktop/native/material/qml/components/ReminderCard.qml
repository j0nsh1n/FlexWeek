import QtQuick

// A reminder the app keeps on screen when the computer shows no system notifications: the block's words, with
// Snooze and Got it. It stays until closed or the block starts, so no timer ends it, and it never takes the
// keyboard when it arrives: Tab reaches the two actions in the page's order.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string message: ""
    signal snoozeClicked()
    signal closeClicked()

    implicitHeight: 56
    height: 56
    implicitWidth: Math.max(320, messageText.implicitWidth + actions.width + 48)
    width: implicitWidth

    M3Palette { id: pal; theme: root.theme }

    Accessible.role: Accessible.AlertMessage
    Accessible.name: root.message

    Rectangle {
        objectName: "shape"
        anchors.fill: parent
        radius: 4
        color: pal.inverseSurface
        // Takes the presses on the card so a click on it never reaches the Week grid underneath.
        TapHandler { gesturePolicy: TapHandler.WithinBounds }
    }
    Text {
        id: messageText
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.right: actions.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: root.message
        elide: Text.ElideRight
        color: pal.inverseOnSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        font.weight: 400
    }
    Row {
        id: actions
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4
        Repeater {
            model: [
                { name: "reminderSnooze", label: "Snooze", access: "Snooze this reminder for 5 minutes", snooze: true },
                { name: "reminderClose", label: "Got it", access: "Got it", snooze: false }
            ]
            delegate: Item {
                id: action
                objectName: modelData.name
                property bool keyDown: false
                width: label.implicitWidth + 24
                height: 36
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: modelData.access
                Accessible.onPressAction: action.press()
                function press() {
                    if (modelData.snooze)
                        root.snoozeClicked()
                    else
                        root.closeClicked()
                }
                Text {
                    id: label
                    anchors.centerIn: parent
                    text: modelData.label
                    color: pal.inversePrimary
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    font.weight: 500
                }
                M3StateLayer {
                    anchors.fill: parent
                    radius: 18
                    color: pal.inversePrimary
                    hovered: hover.hovered
                    down: tap.pressed || action.keyDown
                    reduceMotion: root.reduceMotion
                }
                M3FocusRing { anchors.fill: parent; anchors.margins: -4; target: action; ring: pal.focusRing; ringRadius: 22 }
                HoverHandler { id: hover }
                TapHandler { id: tap; onTapped: action.press() }
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        action.keyDown = true
                        event.accepted = true
                    }
                }
                Keys.onReleased: (event) => {
                    if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (action.keyDown)
                            action.press()
                        action.keyDown = false
                        event.accepted = true
                    }
                }
            }
        }
    }
}
