import QtQuick
import components 1.0

Item {
    id: root
    objectName: "dayMonthSide"
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    property bool passive: false
    property bool open: true
    property int year: 2026
    property int month: 11
    property int today: 0
    property var board

    visible: !phone
    width: phone ? 0 : (open ? 272 : 64)
    clip: true
    Accessible.role: Accessible.Pane
    Accessible.name: "Month"

    Behavior on width {
        NumberAnimation {
            duration: root.reduceMotion ? 0 : 300
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        anchors.fill: parent
        color: palette.surfaceContainerLow
    }

    IconButton {
        objectName: "dayMonthToggle"
        x: 8
        y: 8
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        icon: root.open ? "chevron_left" : "calendar_month"
        accessName: root.open ? "Hide the month" : "Show the month"
        activeFocusOnTab: !root.passive
        onClicked: root.open = !root.open
    }

    MiniMonth {
        objectName: "dayMiniMonth"
        x: 16
        y: 64
        visible: root.open
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        year: root.year
        month: root.month
        today: root.today
        accessName: "Month"
        activeFocusOnTab: !root.passive
        onDayActivated: (day) => {
            if (root.board)
                root.board.pickDay(day)
        }
    }
}
