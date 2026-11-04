import QtQuick
import components 1.0

// One block on the grid. Homework blocks answer a click or Space with "finished".
Item {
    id: cell
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string category: "homework"
    property string title: ""
    property string detail: ""
    property bool past: false
    property bool done: false
    property bool fresh: false
    property bool homework: false
    signal toggled()
    signal opened()
    signal menuAsked(real x, real y)

    M3Palette { id: m3; theme: cell.theme }

    EventBlock {
        id: blockContent
        width: cell.width
        height: cell.height
        theme: cell.theme
        density: cell.density
        reduceMotion: cell.reduceMotion
        highContrast: cell.highContrast
        category: cell.category
        title: cell.title
        detail: cell.detail
        past: cell.past
        accessName: cell.title
    }

    function findTitle(item) {
        if (!item) return null
        if (item.objectName === "title" && item.font !== undefined) return item
        if (item.children) {
            for (var i = 0; i < item.children.length; i++) {
                var found = findTitle(item.children[i])
                if (found) return found
            }
        }
        return null
    }

    function updateStrikeout() {
        var t = findTitle(blockContent)
        if (t) {
            t.font.strikeout = (cell.homework && cell.done)
        }
    }

    onDoneChanged: updateStrikeout()
    onHomeworkChanged: updateStrikeout()

    Item {
        id: finishButton
        objectName: "weekBlockFinish"
        visible: cell.homework
        width: 24
        height: 24
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 4
        activeFocusOnTab: cell.homework
        Accessible.role: Accessible.Button
        Accessible.name: cell.done ? "Open " + cell.title + " again" : "Mark " + cell.title + " finished"
        Accessible.onPressAction: cell.toggled()

        Rectangle {
            id: finishCircle
            anchors.fill: parent
            radius: width / 2
            color: cell.done ? m3.primary : "transparent"
            border.width: cell.done ? 0 : (cell.highContrast ? 1.5 : 1)
            border.color: cell.done ? "transparent" : m3.outline
        }

        M3Icon {
            anchors.centerIn: parent
            name: "check"
            width: 16
            height: 16
            color: cell.done ? m3.inkPrimary : m3.inkMuted
        }

        M3FocusRing {
            anchors.fill: parent
            anchors.margins: -2
            shown: finishButton.activeFocus
            ring: m3.primary
            ringRadius: 14
        }

        HoverHandler {
            cursorShape: Qt.PointingHandCursor
        }

        TapHandler {
            gesturePolicy: TapHandler.WithinBounds
            onTapped: cell.toggled()
        }

        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                cell.toggled()
                event.accepted = true
            }
        }
    }

    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -2
        shown: cell.activeFocus
        ring: m3.primary
        ringRadius: 14
    }

    HoverHandler { enabled: cell.homework; cursorShape: Qt.PointingHandCursor }
    TapHandler { enabled: cell.homework; onTapped: cell.opened() }
    TapHandler {
        acceptedButtons: Qt.RightButton
        enabled: cell.homework
        onTapped: (point) => cell.menuAsked(point.position.x, point.position.y)
    }

    activeFocusOnTab: homework
    Accessible.role: homework ? Accessible.Button : Accessible.StaticText
    Accessible.name: homework
                     ? ("Edit " + title)
                     : title + (detail !== "" ? ", " + detail : "")
    Accessible.onPressAction: if (cell.homework) cell.opened()
    Keys.onPressed: (event) => {
        if (!cell.homework)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            cell.opened()
            event.accepted = true
        } else if ((event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier)) || event.key === Qt.Key_Menu) {
            cell.menuAsked(width / 2, height / 2)
            event.accepted = true
        }
    }

    // A block that just got a time lands with the emphasized curve.
    Component.onCompleted: {
        updateStrikeout()
        if (fresh && !reduceMotion) land.start()
    }
    ParallelAnimation {
        id: land
        NumberAnimation {
            target: cell; property: "scale"; from: 0.9; to: 1; duration: 500
            easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
        NumberAnimation {
            target: cell; property: "opacity"; from: 0; to: 1; duration: 500
            easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }
}
