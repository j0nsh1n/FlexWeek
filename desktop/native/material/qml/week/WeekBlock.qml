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

    M3Palette { id: m3; theme: cell.theme }

    EventBlock {
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

    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -2
        shown: cell.activeFocus
        ring: m3.primary
        ringRadius: 14
    }

    HoverHandler { enabled: cell.homework; cursorShape: Qt.PointingHandCursor }
    TapHandler { enabled: cell.homework; onTapped: cell.toggled() }

    activeFocusOnTab: homework
    Accessible.role: homework ? Accessible.Button : Accessible.StaticText
    Accessible.name: homework
                     ? (done ? "Open " + title + " again" : "Mark " + title + " finished")
                     : title + (detail !== "" ? ", " + detail : "")
    Accessible.onPressAction: if (cell.homework) cell.toggled()
    Keys.onPressed: (event) => {
        if (cell.homework && (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
            cell.toggled()
            event.accepted = true
        }
    }

    // A block that just got a time lands with the emphasized curve.
    Component.onCompleted: if (fresh && !reduceMotion) land.start()
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
