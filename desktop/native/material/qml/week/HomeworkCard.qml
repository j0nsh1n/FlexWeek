import QtQuick
import components 1.0

// A homework card with no time yet. Dragging it onto the grid gives it one.
Rectangle {
    id: card
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string title: ""
    property string detail: ""
    property string tag: ""
    property string tagKind: "plain"
    property string reason: ""
    signal dragMoved(point scene)
    signal dropped(point scene)
    signal dragStarted()
    // Space or Return: the keyboard's way to give it a time.
    signal activated()

    readonly property int pad: density === "compact" ? 8 : 12
    readonly property bool dragging: drag.active

    M3Palette { id: m3; theme: card.theme }

    implicitHeight: Math.max(56, row.implicitHeight + pad * 2)
    height: implicitHeight
    radius: 12
    color: m3.surfaceContainer
    border.width: highContrast ? 1.5 : 0
    border.color: m3.outline
    opacity: dragging ? 0.4 : 1

    M3StateLayer {
        anchors.fill: parent
        radius: card.radius
        color: m3.inkSurface
        hovered: hover.hovered
        down: drag.active
        reduceMotion: card.reduceMotion
    }

    Row {
        id: row
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: card.pad
        anchors.rightMargin: card.pad
        spacing: 8

        Grid {
            id: grip
            objectName: "grip"
            anchors.verticalCenter: parent.verticalCenter
            columns: 2
            spacing: 3
            Repeater {
                model: 6
                Rectangle { width: 3; height: 3; radius: 1.5; color: m3.inkMuted }
            }
        }

        Column {
            width: parent.width - grip.width - tagBox.width - parent.spacing * 2
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0
            Text {
                objectName: "homeworkTitle"
                width: parent.width
                text: card.title
                color: m3.inkSurface
                wrapMode: Text.WordWrap
                font.family: M3Font.family
                font.pixelSize: 14
                font.weight: 500
            }
            Text {
                objectName: "homeworkDetail"
                width: parent.width
                text: card.detail
                color: m3.inkMuted
                wrapMode: Text.WordWrap
                font.family: M3Font.family
                font.pixelSize: 12
                font.weight: 400
            }
        }

        Item {
            id: tagBox
            width: card.tag !== "" ? chip.width : 0
            height: chip.height
            anchors.verticalCenter: parent.verticalCenter
            Tag {
                id: chip
                objectName: "homeworkTag"
                visible: card.tag !== ""
                theme: card.theme
                density: card.density
                reduceMotion: card.reduceMotion
                highContrast: card.highContrast
                kind: card.tagKind
                text: card.tag
            }
        }
    }

    HoverHandler { id: hover; cursorShape: Qt.OpenHandCursor }
    DragHandler {
        id: drag
        target: null
        cursorShape: Qt.ClosedHandCursor
        onActiveChanged: {
            if (active)
                card.dragStarted()
            else
                card.dropped(centroid.scenePosition)
        }
        onCentroidChanged: if (active) card.dragMoved(centroid.scenePosition)
    }

    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -2
        shown: card.activeFocus
        ring: m3.primary
        ringRadius: 14
    }

    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: title + ", no time yet. Press Space to find a time."
    Accessible.onPressAction: card.activated()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            card.activated()
            event.accepted = true
        }
    }
}
