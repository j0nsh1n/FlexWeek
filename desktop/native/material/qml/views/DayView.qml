import QtQuick
import components 1.0
import day 1.0
import hours 1.0

Item {
    id: root
    objectName: "materialDay"
    property var bridge
    property bool phone: false
    // The shell's page heading, where keyboard focus goes when the Now card goes away holding it.
    property Item pageHeading: null
    property bool passive: false

    readonly property var board: bridge && bridge.day ? bridge.day : null

    // The keyboard back on the day after an Undo, a redo or the notice's Undo: the block acted on when it
    // is still there, else the hours, else the page heading.
    function keptBlockId() {
        return hoursLoader.item ? hoursLoader.item.keptBlockId : ""
    }
    function focusDay(blockId) {
        if (hoursLoader.item && hoursLoader.item.focusWeek)
            hoursLoader.item.focusWeek(blockId)
        else if (root.pageHeading)
            root.pageHeading.forceActiveFocus()
    }
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge && bridge.density ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false
    readonly property int row: bridge && bridge.dayHourRow ? bridge.dayHourRow : 56
    readonly property int dayIndex: board ? board.dayIndex : -1
    readonly property int minSideWidth: 240
    readonly property int maxSideWidth: Math.max(minSideWidth, Math.min(480, Math.floor(width * 0.48)))
    readonly property int rememberedSideWidth: bridge && bridge.daySideWidth ? bridge.daySideWidth : 312
    property int dragSideWidth: -1
    readonly property int sideWidth: Math.max(minSideWidth, Math.min(maxSideWidth, dragSideWidth >= 0 ? dragSideWidth : rememberedSideWidth))
    readonly property int outerPad: phone || passive ? 0 : 12

    // A block's menu is open on Day: the zoom keys wait, as on Week.
    readonly property bool menuOpen: hoursLoader.item ? hoursLoader.item.menuOpen : false
    readonly property bool handing: hoursLoader.item ? hoursLoader.item.handing : false

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

    // Left (main) full-height day timeline pane
    Item {
        id: pane
        anchors.left: parent.left
        anchors.leftMargin: root.outerPad
        anchors.right: root.phone ? parent.right : sideDivider.left
        anchors.rightMargin: root.phone ? 0 : 0
        anchors.top: parent.top
        anchors.topMargin: root.outerPad
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.phone ? 0 : root.outerPad

        Column {
            id: heading
            width: parent.width
            spacing: 10
            topPadding: root.phone ? 12 : 0
            leftPadding: root.phone ? 16 : 0
            rightPadding: root.phone ? 16 : 0
            bottomPadding: 10

            Row {
                width: parent.width - heading.leftPadding - heading.rightPadding
                spacing: 12

                Rectangle {
                    id: dayNavPill
                    height: 36
                    width: dayNavRow.implicitWidth + 8
                    radius: palette.cornerFor(18)
                    color: palette.cardSurface
                    border.width: root.highContrast ? 1.5 : 1
                    border.color: root.highContrast ? palette.outline : palette.outlineVariant

                    Row {
                        id: dayNavRow
                        anchors.centerIn: parent
                        spacing: 0
                        IconButton {
                            objectName: "dayPrevious"
                            small: true
                            anchors.verticalCenter: parent.verticalCenter
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
                            small: true
                            anchors.verticalCenter: parent.verticalCenter
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
                }

                Text {
                    objectName: "dayLeftLine"
                    width: Math.max(0, parent.width - dayNavPill.width - parent.spacing)
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.board ? root.board.leftLine : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(15)
                    font.weight: 500
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }
            }

            // On phone widths, NowCard stacks above the timeline; on desktop it lives in the right panel.
            Item {
                id: phoneNowSlot
                visible: root.phone && nowCard.shown
                width: heading.width - heading.leftPadding - heading.rightPadding
                height: visible ? nowCard.height : 0
            }
        }

        Rectangle {
            id: hoursCard
            objectName: "dayHoursCard"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: heading.bottom
            anchors.bottom: parent.bottom
            radius: root.phone ? 0 : palette.cornerFor(16)
            color: palette.cardSurface
            border.width: root.phone ? 0 : (root.highContrast ? 1.5 : 1)
            border.color: root.highContrast ? palette.outline : palette.outlineVariant
            clip: true

            Loader {
                id: hoursLoader
                anchors.fill: parent
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
    }

    // Draggable and keyboard-operable vertical divider between Day timeline (left) and Now + Month panel (right).
    Item {
        id: sideDivider
        objectName: "daySideDivider"
        visible: !root.phone
        anchors.right: rightPanel.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 12
        activeFocusOnTab: !root.phone && !root.passive
        Accessible.role: Accessible.Slider
        Accessible.name: "Resize day sidebar"
        Accessible.description: "Use Left and Right arrow keys to resize"

        function stepResize(delta) {
            if (root.passive || !root.bridge || !root.bridge.setDaySideWidth)
                return
            var next = Math.max(root.minSideWidth, Math.min(root.maxSideWidth, root.sideWidth + delta))
            if (next !== root.sideWidth)
                root.bridge.setDaySideWidth(next)
        }

        M3FocusRing {
            anchors.centerIn: parent
            width: 10
            height: 56
            ring: palette.focusRing
            ringRadius: 5
        }

        Rectangle {
            anchors.centerIn: parent
            width: dividerMouse.containsMouse || dividerMouse.pressed || sideDivider.activeFocus ? 4 : 2
            height: dividerMouse.containsMouse || dividerMouse.pressed || sideDivider.activeFocus ? 48 : 32
            radius: width / 2
            color: dividerMouse.containsMouse || dividerMouse.pressed || sideDivider.activeFocus ? palette.primary : palette.outlineVariant
        }

        Keys.onPressed: (event) => {
            var step = (event.modifiers & Qt.ShiftModifier) ? 40 : 16
            if (event.key === Qt.Key_Left) {
                sideDivider.stepResize(step)
                event.accepted = true
            } else if (event.key === Qt.Key_Right) {
                sideDivider.stepResize(-step)
                event.accepted = true
            } else if (event.key === Qt.Key_Home) {
                sideDivider.stepResize(root.minSideWidth - root.sideWidth)
                event.accepted = true
            } else if (event.key === Qt.Key_End) {
                sideDivider.stepResize(root.maxSideWidth - root.sideWidth)
                event.accepted = true
            }
        }

        MouseArea {
            id: dividerMouse
            anchors.fill: parent
            enabled: !root.passive
            hoverEnabled: true
            cursorShape: Qt.SplitHCursor
            property real pressSceneX: 0
            property int pressWidth: 312
            property bool moved: false
            onPressed: (mouse) => {
                pressSceneX = mapToItem(root, mouse.x, 0).x
                pressWidth = root.sideWidth
                moved = false
            }
            onPositionChanged: (mouse) => {
                if (!pressed)
                    return
                var curX = mapToItem(root, mouse.x, 0).x
                var delta = pressSceneX - curX
                var next = Math.max(root.minSideWidth, Math.min(root.maxSideWidth, Math.round(pressWidth + delta)))
                if (Math.abs(delta) >= 1 && next !== pressWidth) {
                    moved = true
                    root.dragSideWidth = next
                } else if (moved) {
                    root.dragSideWidth = next
                }
            }
            onReleased: {
                if (moved && root.dragSideWidth >= 0 && root.dragSideWidth !== pressWidth
                    && root.bridge && root.bridge.setDaySideWidth)
                    root.bridge.setDaySideWidth(root.dragSideWidth)
                moved = false
                root.dragSideWidth = -1
            }
            onCanceled: {
                moved = false
                root.dragSideWidth = -1
            }
        }
    }

    // Right sidebar: Now focus card above the collapsible mini-month calendar.
    Flickable {
        id: rightPanel
        objectName: "dayRightPanel"
        visible: !root.phone
        anchors.right: parent.right
        anchors.rightMargin: root.outerPad
        anchors.top: parent.top
        anchors.topMargin: root.outerPad
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.outerPad
        width: root.phone ? 0 : root.sideWidth
        contentWidth: width
        contentHeight: rightColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: rightColumn
            width: rightPanel.width
            spacing: 12

            Item {
                id: desktopNowSlot
                visible: !root.phone && nowCard.shown
                width: parent.width
                height: visible ? nowCard.height : 0
            }

            MonthSide {
                id: side
                width: parent.width
                passive: root.passive
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
        }
    }

    NowCard {
        id: nowCard
        parent: root.phone ? phoneNowSlot : desktopNowSlot
        width: parent ? parent.width : 280
        passive: root.passive
        shown: !!(root.board && root.board.showNow)
        pageHeading: root.pageHeading
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        timerTitle: root.board ? root.board.timerTitle : ""
        timerLine: root.board ? root.board.timerLine : ""
        timerEnded: root.board ? root.board.timerEnded : false
        timerCanFinish: root.board ? root.board.timerCanFinish : false
        timerDone: root.board ? root.board.timerDone : false
        scope: "day"
        title: root.board ? root.board.nowTitle : ""
        focusTitle: root.board ? root.board.focusTitle : ""
        busy: !!(root.board && root.board.nowBusy)
        line: root.board ? root.board.nowLine : ""
        onStartFocus: if (root.board) root.board.startFocus()
        onMarkFinished: if (root.board) root.board.markFinished()
        onStartAgain: if (root.board) root.board.startAgain()
        onDismissFinished: if (root.board) root.board.dismissFinished()
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
