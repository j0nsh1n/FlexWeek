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
    implicitWidth: Math.max(240, miniMonth.width + 32)
    implicitHeight: open ? (headerBar.height + miniMonth.height + 20) : (headerBar.height + 16)
    height: implicitHeight
    clip: true
    Accessible.role: Accessible.Pane
    Accessible.name: "Month"

    Behavior on height {
        NumberAnimation {
            duration: Motion.travel(220, root.reduceMotion)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        anchors.fill: parent
        radius: palette.cornerFor(16)
        color: palette.cardSurface
        border.width: root.highContrast ? 1.5 : 1
        border.color: root.highContrast ? palette.outline : palette.outlineVariant
    }

    Item {
        id: headerBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 16
        anchors.rightMargin: 8
        anchors.topMargin: 8
        height: 36

        Text {
            anchors.left: parent.left
            anchors.right: toggleBtn.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: miniMonth.monthName()
            elide: Text.ElideRight
            color: palette.inkSurface
            font.family: M3Font.heading
            font.pixelSize: M3Font.px(15)
            font.weight: 600
        }

        IconButton {
            id: toggleBtn
            objectName: "dayMonthToggle"
            small: true
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: root.open ? "chevron_left" : "calendar_month"
            accessName: root.open ? "Hide the month" : "Show the month"
            activeFocusOnTab: !root.passive
            onClicked: root.open = !root.open
        }
    }

    MiniMonth {
        id: miniMonth
        objectName: "dayMiniMonth"
        anchors.horizontalCenter: parent.horizontalCenter
        y: headerBar.y + headerBar.height + 4
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
