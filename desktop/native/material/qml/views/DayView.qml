import QtQuick
import components 1.0
import day 1.0
import hours 1.0

Item {
    id: root
    objectName: "materialDay"
    property var bridge
    property bool phone: false
    property bool passive: false

    readonly property var board: bridge && bridge.day ? bridge.day : null
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge && bridge.density ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false
    readonly property int row: bridge && bridge.dayHourRow ? bridge.dayHourRow : 56
    readonly property int dayIndex: board ? board.dayIndex : -1

    // A block's menu is open on Day: the zoom keys wait, as on Week.
    readonly property bool menuOpen: hoursLoader.item ? hoursLoader.item.menuOpen : false

    function zoomFromKeys(steps) {
        if (hoursLoader.item)
            hoursLoader.item.zoomFromKeys(steps)
    }

    function resetZoomFromKeys() {
        if (hoursLoader.item)
            hoursLoader.item.resetZoomFromKeys()
    }

    function zoomAbout(steps, viewY) {
        if (hoursLoader.item)
            hoursLoader.item.zoomAbout(steps, viewY)
    }

    // The page's heading for screen readers. The top bar already shows the title.
    Text {
        objectName: "screenTitle"
        width: 1
        height: 1
        opacity: 0
        text: "Day"
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        Accessible.role: Accessible.Heading
        Accessible.name: text
    }

    MonthSide {
        id: side
        passive: root.passive
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        phone: root.phone
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        board: root.board
        year: root.board ? root.board.year : 2026
        month: root.board ? root.board.month : 1
        today: root.board ? root.board.miniDay : 0
    }

    Item {
        id: pane
        anchors.left: side.visible ? side.right : parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        Column {
            id: heading
            width: parent.width
            spacing: 12
            topPadding: root.phone ? 16 : 24
            leftPadding: root.phone ? 16 : 24
            rightPadding: root.phone ? 16 : 24

            Row {
                spacing: 4
                IconButton {
                    objectName: "dayPrevious"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "chevron_left"
                    accessName: "Previous day"
                    activeFocusOnTab: !root.passive
                    onClicked: if (root.board) root.board.previousDay()
                }
                IconButton {
                    objectName: "dayNext"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "chevron_right"
                    accessName: "Next day"
                    activeFocusOnTab: !root.passive
                    onClicked: if (root.board) root.board.nextDay()
                }
            }

            Text {
                objectName: "dayLeftLine"
                width: heading.width - heading.leftPadding - heading.rightPadding
                text: root.board ? root.board.leftLine : ""
                wrapMode: Text.WordWrap
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(16)
                font.weight: 400
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }

            NowCard {
                width: heading.width - heading.leftPadding - heading.rightPadding
                passive: root.passive
                visible: root.board && root.board.showNow
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                timerTitle: root.board ? root.board.timerTitle : ""
                timerLine: root.board ? root.board.timerLine : ""
                scope: "day"
                title: root.board ? root.board.nowTitle : ""
                focusTitle: root.board ? root.board.focusTitle : ""
                line: root.board ? root.board.nowLine : ""
                onStartFocus: if (root.board) root.board.startFocus()
            }
        }

        Loader {
            id: hoursLoader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: heading.bottom
            anchors.bottom: parent.bottom
            active: root.passive || (root.bridge && root.bridge.screen === "day")
            sourceComponent: HoursPane {
                bridge: root.bridge
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                passive: root.passive
                phone: root.phone
                row: root.row
                columns: 1
                filterDay: root.dayIndex
                showNowLine: root.dayIndex >= 0 && root.bridge && root.bridge.nowDay === root.dayIndex
                showPill: true
                weekMode: false
                followOpening: true
                openingMinute: root.board ? root.board.openingMinute : 480
                scrollClearance: root.phone ? 96 : 0
                scrollerName: "dayScroller"
            }
        }
    }

    M3Palette { id: palette; theme: root.theme }

    onVisibleChanged: {
        if (visible && hoursLoader.item)
            hoursLoader.item.revealOpening(true)
    }

    Connections {
        target: root.board
        function onDateOpened() {
            if (hoursLoader.item)
                hoursLoader.item.revealOpening(true)
        }
    }
}
