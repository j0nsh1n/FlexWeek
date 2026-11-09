import QtQuick
import components 1.0

// One block on the grid. Every block opens, in Week as in Day (Jonathan, 2026-11-08); Day sets dayOpen
// so Space finishes homework there.
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
    property bool passive: false
    // Day sets this: there Space finishes homework, in Week it opens it.
    property bool dayOpen: false
    // Drawn over a block it shares time with: an opaque base keeps the one under it from showing
    // through, and a light shadow (an outline on a dark surface, where a shadow does not show) sets it
    // apart.
    property bool raised: false
    // Another block lies on this one. Its words go where they show (wordsTop, within wordsRoom), or,
    // with nowhere to go, its name runs up its uncovered strip, `sideStrip` wide, on its side.
    property bool nameSide: false
    property real sideStrip: 0
    property real wordsTop: 0
    property real wordsRoom: -1
    readonly property bool keyFocus: finishButton.activeFocus
    readonly property bool canOpen: !cell.passive
    signal toggled()
    signal opened()
    signal menuAsked(real x, real y)
    signal focused()

    M3Palette { id: m3; theme: cell.theme }

    // The title's column is the block minus its 12 px left and 8 px right padding. When the circle on
    // the title row would leave it less than three wide letters, the circle moves to the block's
    // bottom-right corner so the title keeps the whole column. It also moves on any block where it
    // would cut the title short, whether or not the block shares time (recheck M7: "Scie..."; Jonathan,
    // 2026-11-08, option A: a corner circle, never hidden unless the block is too short for it).
    FontMetrics {
        id: titleMetrics
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        font.weight: 600
    }
    Text {
        id: besideCircle
        visible: false
        width: Math.max(0, cell.width - 20 - 28)
        text: cell.title
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        maximumLineCount: blockContent.titleLines
        elide: Text.ElideRight
        font: titleMetrics.font
        lineHeight: 1.25
        lineHeightMode: Text.ProportionalHeight
    }
    readonly property bool circleCorner: cell.homework
                                        && (cell.width - 20 - 28 < titleMetrics.advanceWidth("MMM")
                                            || besideCircle.truncated)
    // The corner circle is sized with the text, never under 20 px so it stays a clear click target.
    readonly property real cornerSize: Math.max(20, Math.ceil(blockContent.titleLine))
    // The circle shows whole where the words show, or not at all: a block too short for it below its
    // title, or one whose name is on its side, hides it. Edit, the right-click menu and Shift+F10 still
    // finish the homework.
    readonly property real wordsEnd: cell.wordsRoom >= 0 ? cell.wordsTop + cell.wordsRoom : cell.height
    readonly property real cornerTop: cell.wordsEnd - cell.cornerSize - 3
    readonly property bool circleFits: !cell.nameSide
                                       && (cell.circleCorner
                                           ? cell.cornerTop >= blockContent.titleBottom
                                           : cell.wordsTop + 4 + finishButton.height + 2 <= cell.wordsEnd)
    // The corner circle lies beside the time line, which then gives up its right end rather than run
    // under the circle; where the circle sits below the time line it takes nothing from it.
    readonly property bool circleBesideTime: cell.circleCorner && cell.circleFits
                                             && cell.cornerTop < blockContent.contentBottom

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
        rightInset: cell.homework && !cell.circleCorner && cell.circleFits ? 28 : 0
        detailInset: cell.circleBesideTime ? cell.cornerSize + 8 : 0
        fitToHeight: true
        wordsTop: cell.wordsTop
        wordsRoom: cell.wordsRoom
        showWords: !cell.nameSide
    }

    // The name on its side, reading upward in the strip left of the block that lies on this one.
    Text {
        objectName: "sideName"
        visible: cell.nameSide
        transformOrigin: Item.TopLeft
        rotation: -90
        x: 4 + 3
        y: cell.height - blockContent.pad
        width: Math.max(0, cell.height - 2 * blockContent.pad)
        height: Math.ceil(titleMetrics.height)
        text: cell.title
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        color: blockContent.textInk
        font: titleMetrics.font
    }

    Rectangle {
        objectName: "overlapShadow"
        z: -2
        visible: cell.raised && !blockContent.darkSurface
        x: -1
        y: 1
        width: cell.width + 2
        height: cell.height + 2
        radius: blockContent.cornerRadius + 1
        color: "#000000"
        opacity: 0.16
    }

    Rectangle {
        z: -1
        visible: cell.raised
        anchors.fill: parent
        radius: blockContent.cornerRadius
        color: m3.surfaceContainerLowest
    }

    Rectangle {
        objectName: "overlapOutline"
        visible: cell.raised && blockContent.darkSurface
        anchors.fill: parent
        radius: blockContent.cornerRadius
        color: "transparent"
        border.width: 1
        border.color: m3.outline
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
        visible: cell.homework && cell.circleFits
        width: cell.circleCorner ? cell.cornerSize : 24
        height: width
        x: cell.width - width - 4
        y: cell.circleCorner ? cell.cornerTop : cell.wordsTop + 4
        activeFocusOnTab: !cell.passive && cell.homework && cell.circleFits
        onActiveFocusChanged: if (activeFocus) cell.focused()
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
            width: cell.circleCorner ? 14 : 16
            height: width
            color: cell.done ? m3.inkPrimary : m3.inkMuted
        }

        M3FocusRing {
            anchors.fill: parent
            anchors.margins: -4
            target: finishButton
            ring: m3.focusRing
            ringRadius: finishButton.width / 2 + 4
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
        anchors.margins: -4
        ring: m3.focusRing
        ringRadius: 14
    }

    HoverHandler { enabled: cell.canOpen; cursorShape: Qt.PointingHandCursor }
    // A block can lie over another: the one on top takes the tap, so the one under it does not open too.
    TapHandler { enabled: cell.canOpen; gesturePolicy: TapHandler.WithinBounds; onTapped: cell.opened() }
    TapHandler {
        acceptedButtons: Qt.RightButton
        enabled: cell.homework
        gesturePolicy: TapHandler.WithinBounds
        onTapped: (point) => cell.menuAsked(point.position.x, point.position.y)
    }

    activeFocusOnTab: cell.canOpen
    onActiveFocusChanged: if (activeFocus) cell.focused()
    Accessible.role: cell.canOpen ? Accessible.Button : Accessible.StaticText
    Accessible.name: cell.canOpen
                     ? ("Edit " + title)
                     : title + (detail !== "" ? ", " + detail : "")
    Accessible.onPressAction: if (cell.canOpen) cell.opened()
    Keys.onPressed: (event) => {
        if (!cell.canOpen)
            return
        if (cell.dayOpen && cell.homework && event.key === Qt.Key_Space) {
            cell.toggled()
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                   || (event.key === Qt.Key_Space && !cell.dayOpen)) {
            cell.opened()
            event.accepted = true
        } else if ((event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier)) || event.key === Qt.Key_Menu) {
            if (cell.homework) {
                cell.menuAsked(width / 2, height / 2)
                event.accepted = true
            }
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
