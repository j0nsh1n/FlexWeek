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
    signal activated()
    signal opened()
    signal menuAsked(real x, real y)

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

    property bool wasDragged: false

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler {
        id: tap
        onTapped: {
            if (!card.wasDragged)
                card.opened()
            card.wasDragged = false
        }
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: (point) => card.menuAsked(point.position.x, point.position.y)
    }
    DragHandler {
        id: drag
        target: null
        dragThreshold: 4
        cursorShape: Qt.ClosedHandCursor
        onActiveChanged: {
            if (active) {
                card.wasDragged = true
                card.dragStarted()
            } else {
                card.dropped(centroid.scenePosition)
                Qt.callLater(function() { card.wasDragged = false })
            }
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
    Accessible.name: "Edit " + title
    Accessible.onPressAction: card.opened()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            card.opened()
            event.accepted = true
        } else if ((event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier)) || event.key === Qt.Key_Menu) {
            card.menuAsked(width / 2, height / 2)
            event.accepted = true
        }
    }
}
