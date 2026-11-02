import QtQuick
import QtQuick.Layouts
import components 1.0
import "views"
import "account"
import "focus"
import "sheets"

Item {
    id: root
    objectName: "materialShell"
    // Set before the shell is created. A context property was null by the time these bindings ran.
    property var bridge
    readonly property bool phone: width < 768
    readonly property var theme: bridge ? bridge.theme : ({})
    readonly property string density: bridge ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false
    readonly property int enterMs: reduceMotion ? 0 : 300
    readonly property bool typing: sheetHost.active || _field(Window.activeFocusItem)
    // The Focus screen covers the window. The number keys, Z and Esc belong to it while it is open.
    readonly property bool focusOpen: bridge ? bridge.focus.open : false

    function _field(item) {
        while (item) {
            if (item instanceof TextInput || item instanceof TextEdit)
                return true
            item = item.parent
        }
        return false
    }

    function focusDestination() {
        var item = navWeekRail
        if (bridge.screen === "day")
            item = phone ? navDayBar : navDayRail
        else if (bridge.screen === "week")
            item = phone ? navWeekBar : navWeekRail
        else if (bridge.screen === "month")
            item = phone ? navMonthPhone : navMonthRail
        else if (bridge.screen === "myday")
            item = phone ? navMyDayBar : navMyDayRail
        else
            item = phone ? navSettingsBar : navSettingsRail
        item.forceActiveFocus()
    }

    function takeKey(event) {
        if (typing || focusOpen || accountLayer.active || bridge.shortcuts === false)
            return
        var key = event.key
        var plain = !(event.modifiers & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))
        if (key === Qt.Key_1)
            bridge.showPage("day")
        else if (key === Qt.Key_2)
            bridge.showPage("week")
        else if (key === Qt.Key_3)
            bridge.showPage("month")
        else if (key === Qt.Key_4)
            bridge.showPage("myday")
        else if (key === Qt.Key_5)
            bridge.showPage("settings")
        else if (key === Qt.Key_Z && plain)
            bridge.undo()
        else if (key === Qt.Key_F)
            bridge.focus.show()
        else if (key === Qt.Key_P && plain)
            bridge.plan()
        else if (key === Qt.Key_Escape)
            focusDestination()
        else
            return
        event.accepted = true
    }

    focus: true
    Keys.onPressed: (event) => takeKey(event)

    Rectangle {
        anchors.fill: parent
        color: root.theme.surface
    }

    Row {
        anchors.fill: parent
        spacing: 0
        visible: !accountLayer.active

        NavRail {
            id: rail
            objectName: root.phone ? "" : "materialRail"
            visible: !root.phone
            width: root.phone ? 0 : 80
            height: parent.height
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast

            Fab {
                id: railFab
                objectName: root.phone ? "" : "materialFab"
                visible: !root.phone
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "add"
                accessName: "Add homework"
                onClicked: bridge.addHomework()
            }

            NavDestination {
                id: navDayRail
                objectName: root.phone ? "" : "navDay"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "calendar_view_day"
                label: "Day"
                accessName: "Day"
                selected: bridge.screen === "day"
                onActivated: bridge.showPage("day")
            }

            NavDestination {
                id: navWeekRail
                objectName: root.phone ? "" : "navWeek"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "calendar_view_week"
                label: "Week"
                accessName: "Week"
                selected: bridge.screen === "week"
                onActivated: bridge.showPage("week")
            }

            NavDestination {
                id: navMonthRail
                objectName: root.phone ? "" : "navMonth"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "calendar_month"
                label: "Month"
                accessName: "Month"
                selected: bridge.screen === "month"
                onActivated: bridge.showPage("month")
            }

            NavDestination {
                id: navMyDayRail
                objectName: root.phone ? "" : "navMyDay"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "task_alt"
                label: "My day"
                accessName: "My day"
                selected: bridge.screen === "myday"
                onActivated: bridge.showPage("myday")
            }

            NavDestination {
                id: navSettingsRail
                objectName: root.phone ? "" : "navSettings"
                pinned: true
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "settings"
                label: "Settings"
                accessName: "Settings"
                selected: bridge.screen === "settings"
                onActivated: bridge.showPage("settings")
            }
        }

        Item {
            id: body
            width: parent.width - (root.phone ? 0 : rail.width)
            height: parent.height

            Rectangle {
                id: topBar
                objectName: "materialTop"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 64
                color: root.theme.surface

                Text {
                    id: title
                    objectName: "materialTitle"
                    anchors.left: parent.left
                    anchors.leftMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: tools.left
                    text: bridge.title
                    color: root.theme.onSurface
                    font.family: "Roboto Flex"
                    font.pixelSize: 22
                    font.weight: 500
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }

                Row {
                    id: tools
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4

                    Text {
                        objectName: "materialClock"
                        height: 48
                        verticalAlignment: Text.AlignVCenter
                        text: bridge.clockText
                        color: root.theme.onSurface
                        font.family: "Roboto Flex"
                        font.pixelSize: 16
                        font.weight: 500
                    }

                    IconButton {
                        id: navMonthPhone
                        objectName: root.phone ? "navMonth" : ""
                        visible: root.phone
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "calendar_month"
                        accessName: "Month"
                        onClicked: bridge.showPage("month")
                    }

                    IconButton {
                        objectName: "materialUndo"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "undo"
                        accessName: "Undo"
                        enabled: bridge.canUndo
                        onClicked: bridge.undo()
                    }

                    IconButton {
                        objectName: "materialRedo"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "redo"
                        accessName: "Redo"
                        enabled: bridge.canRedo
                        onClicked: bridge.redo()
                    }

                    IconButton {
                        objectName: "materialMore"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "more_vert"
                        accessName: "More"
                        onClicked: bridge.openMore()
                    }
                }
            }

            Item {
                id: stage
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: topBar.bottom
                anchors.bottom: root.phone ? bar.top : parent.bottom
                opacity: 1

                StackLayout {
                    id: pages
                    anchors.fill: parent
                    currentIndex: bridge.pageIndex

                    DayView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        bridge: root.bridge
                        phone: root.phone
                    }
                    WeekView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        bridge: root.bridge
                        phone: root.phone
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                    }
                    MonthView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        bridge: root.bridge
                        phone: root.phone
                    }
                    MyDayView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        bridge: root.bridge
                        phone: root.phone
                    }
                    SettingsView { Layout.fillWidth: true; Layout.fillHeight: true; bridge: root.bridge }
                }

                NumberAnimation {
                    id: enter
                    target: stage
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: root.enterMs
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
                }
            }

            NavBar {
                id: bar
                objectName: root.phone ? "materialBar" : ""
                visible: root.phone
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: parent.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast

                NavDestination {
                    id: navDayBar
                    objectName: root.phone ? "navDay" : ""
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "calendar_view_day"
                    label: "Today"
                    accessName: "Day"
                    selected: bridge.screen === "day"
                    onActivated: bridge.showPage("day")
                }

                NavDestination {
                    id: navWeekBar
                    objectName: root.phone ? "navWeek" : ""
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "calendar_view_week"
                    label: "Week"
                    accessName: "Week"
                    selected: bridge.screen === "week"
                    onActivated: bridge.showPage("week")
                }

                NavDestination {
                    id: navMyDayBar
                    objectName: root.phone ? "navMyDay" : ""
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "task_alt"
                    label: "My day"
                    accessName: "My day"
                    selected: bridge.screen === "myday"
                    onActivated: bridge.showPage("myday")
                }

                NavDestination {
                    id: navSettingsBar
                    objectName: root.phone ? "navSettings" : ""
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "settings"
                    label: "Settings"
                    accessName: "Settings"
                    selected: bridge.screen === "settings"
                    onActivated: bridge.showPage("settings")
                }
            }

            Fab {
                id: phoneFab
                objectName: root.phone ? "materialFab" : ""
                visible: root.phone
                z: 2
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 96
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "add"
                accessName: "Add homework"
                onClicked: bridge.addHomework()
            }

            Snackbar {
                objectName: "materialSnackbar"
                visible: bridge.snackText !== ""
                z: 3
                message: bridge.snackText
                onActionClicked: bridge.undo()
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.phone ? 96 : 24
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
            }
        }
    }

    FocusScreen {
        id: focusOverlay
        anchors.fill: parent
        bridge: root.bridge
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
    }

    SheetHost {
        id: sheetHost
        z: 30
        bridge: root.bridge
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        phone: root.phone
        onRestoreFocus: root.focusDestination()
    }

    // A clock tick also emits changed. The enter animation follows the screen only.
    property string shownScreen: bridge.screen
    onShownScreenChanged: enter.restart()

    Shortcut {
        sequence: "1"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.showPage("day")
    }
    Shortcut {
        sequence: "2"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.showPage("week")
    }
    Shortcut {
        sequence: "3"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.showPage("month")
    }
    Shortcut {
        sequence: "4"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.showPage("myday")
    }
    Shortcut {
        sequence: "5"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.showPage("settings")
    }
    Shortcut {
        sequence: "Z"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.undo()
    }
    Shortcut {
        sequence: "F"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.focus.show()
    }
    Shortcut {
        sequence: "P"
        context: Qt.WindowShortcut
        enabled: !typing && !accountLayer.active && !focusOpen && bridge.shortcuts !== false
        onActivated: bridge.plan()
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: !accountLayer.active && !focusOverlay.ending && !sheetHost.active
        onActivated: {
            if (focusOpen)
                bridge.focus.back()
            else
                focusDestination()
        }
    }

    // Sign in, recovery codes and first-run setup cover the shell until the student is in.
    Loader {
        id: accountLayer
        objectName: "accountLayer"
        anchors.fill: parent
        z: 100
        active: root.bridge ? root.bridge.account.phase !== "app" : false
        sourceComponent: AccountFlow {
            bridge: root.bridge.account
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
        }
    }
}
