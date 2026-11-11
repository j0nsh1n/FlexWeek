import QtQuick
import components 1.0
import hours 1.0
import "../week"

Item {
    id: root
    // The settings preview is a second week. It passes another name so the shell week stays findable.
    property string viewName: "materialWeek"
    objectName: viewName
    property var bridge
    property bool phone: false
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool passive: false
    // The floating add button sits 96px up on a phone. The grid can scroll clear of it.
    // A block's or a card's menu is open: the zoom keys leave the grid behind it alone.
    readonly property bool menuOpen: hoursPane.menuOpen || drawer.menuOpen
    readonly property int scrollClearance: phone ? 96 : 0
    readonly property int gutter: hoursPane.hourGutter
    readonly property int drawerWidth: 320
    readonly property real gridWidth: phone ? width : Math.max(0, width - drawerWidth)
    property alias drawer: drawer
    // Five columns with weekends off, seven otherwise. Weekday columns widen by the freed space.
    readonly property int columns: bridge && bridge.week ? Math.max(1, bridge.week.columns) : 7
    readonly property real dayWidth: Math.max(48, (gridWidth - gutter) / columns)
    // The shell clears `bridge` while the page is torn down. These stay readable then.
    readonly property int row: bridge ? bridge.hourRow : 56

    M3Palette { id: m3; theme: root.theme }
    readonly property var line: theme && theme.hourLines === "Clear"
                                ? m3.outline
                                : m3.outlineVariant
    readonly property var now: (theme && theme.nowLine) ? theme.nowLine : m3.error

    // Where a held card would land: -1 when it is not over the grid.
    property int dropDay: -1
    property int dropMinute: -1
    // A card lands on the student's drag step, as a block moved by hand does.
    readonly property int dragStep: bridge && bridge.week && bridge.week.dragStep > 0 ? bridge.week.dragStep : 5
    property string heldTitle: ""
    property point heldAt: Qt.point(0, 0)
    property bool holding: false

    function slotAt(scene) {
        var inScroller = scroller.mapFromItem(null, scene.x, scene.y)
        if (inScroller.x < 0 || inScroller.y < 0 || inScroller.x > scroller.width || inScroller.y > scroller.height)
            return null
        var spot = hours.mapFromItem(null, scene.x, scene.y)
        var day = Math.floor((spot.x - gutter) / dayWidth)
        if (day < 0 || day >= columns || spot.y < 0 || spot.y >= 24 * row)
            return null
        var minute = Math.round(spot.y / row * 60 / dragStep) * dragStep
        return { day: day, minute: Math.max(0, Math.min(24 * 60 - dragStep, minute)) }
    }

    function follow(scene) {
        var local = root.mapFromItem(null, scene.x, scene.y)
        heldAt = Qt.point(local.x, local.y)
        var slot = slotAt(scene)
        dropDay = slot ? slot.day : -1
        dropMinute = slot ? slot.minute : -1
    }

    function release(blockId, scene) {
        var slot = slotAt(scene)
        holding = false
        dropDay = -1
        dropMinute = -1
        if (slot && bridge)
            bridge.week.placeHomework(blockId, slot.day, slot.minute)
    }

    // Drag across empty grid time to add homework.
    property int dragRangeDay: -1
    property int dragRangeStartMin: 0
    property int dragRangeEndMin: 0
    property bool dragRangeActive: false
    property bool dragRangeValid: false
    property bool dragRangeCanceled: false
    property real dragRangePressY: 0

    function snapToQuarter(y) {
        var rawMin = (y / root.row) * 60
        var snapped = Math.round(rawMin / root.dragStep) * root.dragStep
        return Math.max(0, Math.min(24 * 60, snapped))
    }

    function emptyGridTimeAt(x, y) {
        if (x < root.gutter || x >= root.gutter + root.columns * root.dayWidth)
            return false
        if (y < 0 || y >= 24 * root.row)
            return false
        var day = Math.floor((x - root.gutter) / root.dayWidth)
        if (day < 0 || day >= root.columns)
            return false
        if (!bridge || !bridge.blockRows)
            return true
        var rows = bridge.blockRows
        for (var i = 0; i < rows.length; i++) {
            var b = rows[i]
            if (b.day !== day)
                continue
            var by = b.start / 60 * root.row
            var bh = Math.max(36, (b.end - b.start) / 60 * root.row - 2)
            if (y >= by && y <= by + bh)
                return false
        }
        return true
    }

    function cancelDragRange() {
        dragRangeCanceled = true
        dragRangeActive = false
        dragRangeStartMin = 0
        dragRangeEndMin = 0
        dragRangeDay = -1
        if (root.bridge && root.bridge.sheets)
            root.bridge.sheets.setDragRangeActive(false)
    }

    property alias scroller: hoursPane.scroller
    property alias hours: hoursPane.hours

    function zoomAbout(steps, viewY) {
        hoursPane.zoomAbout(steps, viewY)
    }

    function zoomFromKeys(steps) {
        hoursPane.zoomFromKeys(steps)
    }

    function resetZoomFromKeys() {
        hoursPane.resetZoomFromKeys()
    }

    Connections {
        target: root.bridge && root.bridge.sheets ? root.bridge.sheets : null
        function onDragRangeCanceled() {
            root.cancelDragRange()
        }
    }

    Keys.onEscapePressed: (event) => {
        if (root.dragRangeActive) {
            root.cancelDragRange()
            event.accepted = true
        }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        enabled: root.dragRangeActive
        onActivated: root.cancelDragRange()
    }

    Item {
        id: headerRow
        anchors.left: parent.left
        anchors.right: root.phone ? parent.right : drawer.left
        anchors.top: parent.top
        height: 56

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: root.highContrast ? 1.5 : 1
            color: root.line
        }

        IconButton {
            objectName: "toggleWeekends"
            small: !root.phone && !root.passive
            x: Math.round((root.gutter - width) / 2)
            y: root.phone || root.passive ? Math.round((parent.height - height) / 2) : 0
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: "calendar_view_week"
            accessName: root.columns === 7 ? "Hide weekends" : "Show weekends"
            activeFocusOnTab: !root.passive
            onClicked: if (root.bridge) root.bridge.week.toggleWeekends()
        }

        ZoomPill {
            visible: !root.phone && !root.passive
            x: Math.round((root.gutter - width) / 2)
            y: 32
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            canZoomIn: !!(bridge && bridge.canZoomIn)
            canZoomOut: !!(bridge && bridge.canZoomOut)
            onZoomOut: root.zoomFromKeys(-1)
            onZoomIn: root.zoomFromKeys(1)
        }

        Repeater {
            id: dayHeaders
            objectName: "dayHeaders"
            model: bridge ? bridge.days : 0

            Item {
                id: header
                objectName: "dayHeader"
                // "Thu 5": what a reader of the column hears and a test can find.
                property string text: model.label
                readonly property bool today: model.today
                x: root.gutter + index * root.dayWidth
                width: root.dayWidth
                height: 56
                Accessible.role: Accessible.StaticText
                Accessible.name: model.label + (model.today ? ", today" : "")

                Column {
                    anchors.centerIn: parent
                    spacing: 2
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: model.name
                        color: m3.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(12)
                        font.weight: 500
                    }
                    Rectangle {
                        objectName: "dayDate"
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 26
                        height: 26
                        radius: 13
                        color: model.today && !(root.theme && root.theme.todayHighlight === false)
                               ? m3.primary
                               : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: model.date
                            color: parent.color.a > 0 ? m3.inkPrimary : m3.inkSurface
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(14)
                            font.weight: model.today ? 700 : 500
                        }
                    }
                }
            }
        }
    }

    HoursPane {
        id: hoursPane
        anchors.left: parent.left
        anchors.right: root.phone ? parent.right : drawer.left
        anchors.top: headerRow.bottom
        anchors.bottom: root.phone ? drawer.top : parent.bottom
        bridge: root.bridge
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        passive: root.passive
        phone: root.phone
        row: root.row
        gutter: root.gutter
        columns: root.columns
        dayWidth: root.dayWidth
        filterDay: -1
        showNowLine: !!bridge && bridge.nowDay >= 0 && bridge.nowDay < root.columns
        showPill: false
        weekMode: true
        followNow: true
        scrollClearance: root.scrollClearance
        scrollerName: "weekScroller"
        host: root
        dropDay: root.dropDay
        dropMinute: root.dropMinute
    }

    HomeworkDrawer {
        id: drawer
        objectName: "homeworkDrawer"
        passive: root.passive
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: root.phone ? parent.width : root.drawerWidth
        height: root.phone ? Math.min(implicitHeight, Math.max(160, parent.height * 0.45)) : parent.height
        bridge: root.bridge
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        phone: root.phone
        onCardDragStarted: (title) => { root.heldTitle = title; root.holding = true }
        onCardMoved: (scene) => root.follow(scene)
        onCardDropped: (blockId, scene) => root.release(blockId, scene)
    }

    // The card follows the pointer while it is held.
    Rectangle {
        id: ghost
        objectName: "dragGhost"
        visible: root.holding
        z: 20
        x: root.heldAt.x - 24
        y: root.heldAt.y - 16
        width: 168
        height: 32
        radius: 6
        color: m3.primaryContainer
        opacity: 0.92
        Text {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: Text.AlignVCenter
            text: root.heldTitle
            color: m3.inkPrimaryContainer
            elide: Text.ElideRight
            font.family: M3Font.family
            font.pixelSize: M3Font.px(13)
            font.weight: 500
        }
    }
}
