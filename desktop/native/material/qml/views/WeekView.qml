import QtQuick
import components 1.0
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
    readonly property int scrollClearance: phone ? 96 : 0
    readonly property int gutter: 68
    readonly property int drawerWidth: 320
    readonly property real gridWidth: phone ? width : Math.max(0, width - drawerWidth)
    property alias drawer: drawer
    // Five columns with weekends off, seven otherwise. Weekday columns widen by the freed space.
    readonly property int columns: bridge && bridge.week ? Math.max(1, bridge.week.columns) : 7
    readonly property real dayWidth: Math.max(48, (gridWidth - gutter) / columns)
    // The shell clears `bridge` while the page is torn down. These stay readable then.
    readonly property int row: bridge ? bridge.hourRow : 56
    readonly property real typeScale: (theme && theme.typeScale) ? theme.typeScale : 1

    M3Palette { id: m3; theme: root.theme }
    readonly property var line: theme && theme.hourLines === "Clear"
                                ? m3.outline
                                : m3.outlineVariant
    readonly property var now: (theme && theme.nowLine) ? theme.nowLine : m3.error

    // Where a held card would land: -1 when it is not over the grid.
    property int dropDay: -1
    property int dropHour: -1
    property string heldTitle: ""
    property point heldAt: Qt.point(0, 0)
    property bool holding: false

    function slotAt(scene) {
        var inScroller = scroller.mapFromItem(null, scene.x, scene.y)
        if (inScroller.x < 0 || inScroller.y < 0 || inScroller.x > scroller.width || inScroller.y > scroller.height)
            return null
        var spot = hours.mapFromItem(null, scene.x, scene.y)
        var day = Math.floor((spot.x - gutter) / dayWidth)
        var hour = Math.floor(spot.y / row)
        if (day < 0 || day >= columns || hour < 0 || hour > 23)
            return null
        return { day: day, hour: hour }
    }

    function follow(scene) {
        var local = root.mapFromItem(null, scene.x, scene.y)
        heldAt = Qt.point(local.x, local.y)
        var slot = slotAt(scene)
        dropDay = slot ? slot.day : -1
        dropHour = slot ? slot.hour : -1
    }

    function release(blockId, scene) {
        var slot = slotAt(scene)
        holding = false
        dropDay = -1
        dropHour = -1
        if (slot && bridge)
            bridge.week.placeHomework(blockId, slot.day, slot.hour * 60)
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
        var snapped = Math.round(rawMin / 15) * 15
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
            x: 12
            anchors.verticalCenter: parent.verticalCenter
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: "calendar_view_week"
            accessName: root.columns === 7 ? "Hide weekends" : "Show weekends"
            activeFocusOnTab: !root.passive
            onClicked: if (root.bridge) root.bridge.week.toggleWeekends()
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
                        font.pixelSize: 12 * root.typeScale
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
                            font.pixelSize: 14 * root.typeScale
                            font.weight: model.today ? 700 : 500
                        }
                    }
                }
            }
        }
    }

    Flickable {
        id: scroller
        objectName: "weekScroller"
        anchors.left: parent.left
        anchors.right: root.phone ? parent.right : drawer.left
        anchors.top: headerRow.bottom
        anchors.bottom: root.phone ? drawer.top : parent.bottom
        contentWidth: width
        contentHeight: hours.height + root.scrollClearance
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        property string revealedKey: ""

        function reveal(itemY, itemHeight) {
            if (itemY < contentY)
                contentY = Math.max(0, itemY - 8)
            else if (itemY + itemHeight > contentY + height)
                contentY = Math.min(Math.max(0, contentHeight - height), itemY + itemHeight - height + 8)
        }

        function revealNow() {
            if (scroller.moving || scroller.dragging || root.holding)
                return
            var view = height
            if (!bridge || view < 40 || bridge.nowDay < 0)
                return
            var key = bridge.nowDay + ":" + (bridge.week ? bridge.week.columns : 7)
            if (revealedKey === key)
                return
            revealedKey = key
            var row = root.row
            var nowY = bridge.nowMinute / 60 * row
            var earliest = nowY
            var rows = bridge.blockRows || []
            for (var i = 0; i < rows.length; i++) {
                var top = rows[i].start / 60 * row
                if (top < earliest)
                    earliest = top
            }
            var contentY = (nowY - earliest + 48 < view)
                    ? Math.max(0, earliest - 24)
                    : Math.max(0, nowY - view * 0.65)
            var limit = Math.max(0, contentHeight - view)
            scroller.contentY = Math.min(Math.max(0, contentY), limit)
        }

        onHeightChanged: revealNow()

        Connections {
            target: bridge
            function onBlocksChanged() { scroller.revealNow() }
            function onChanged() { scroller.revealNow() }
        }

        Item {
            id: hours
            width: scroller.width
            height: 24 * root.row
            focus: true
            Keys.onEscapePressed: (event) => {
                if (root.dragRangeActive) {
                    root.cancelDragRange()
                    event.accepted = true
                }
            }

            DragHandler {
                id: gridDrag
                target: null
                dragThreshold: 4
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                grabPermissions: PointerHandler.CanTakeOverFromItems | PointerHandler.CanTakeOverFromHandlersOfDifferentType
                onActiveChanged: {
                    if (active) {
                        var px = centroid.pressPosition.x
                        var py = centroid.pressPosition.y
                        if (!root.emptyGridTimeAt(px, py)) {
                            root.dragRangeValid = false
                            root.dragRangeActive = false
                            return
                        }
                        // Only a drag on empty time takes focus, so Escape can cancel it; a block keeps its own.
                        hours.forceActiveFocus()
                        root.dragRangeValid = true
                        root.dragRangeCanceled = false
                        root.dragRangeDay = Math.floor((px - root.gutter) / root.dayWidth)
                        root.dragRangePressY = py
                        var m1 = root.snapToQuarter(py)
                        var m2 = root.snapToQuarter(centroid.position.y)
                        root.dragRangeStartMin = Math.min(m1, m2)
                        root.dragRangeEndMin = Math.max(m1, m2)
                        root.dragRangeActive = true
                        if (root.bridge && root.bridge.sheets)
                            root.bridge.sheets.setDragRangeActive(true)
                    } else {
                        if (root.bridge && root.bridge.sheets)
                            root.bridge.sheets.setDragRangeActive(false)
                        if (root.dragRangeActive && root.dragRangeValid && !root.dragRangeCanceled) {
                            var start = root.dragRangeStartMin
                            var end = root.dragRangeEndMin
                            var day = root.dragRangeDay
                            root.dragRangeActive = false
                            root.dragRangeValid = false
                            if (end - start >= 15 && root.bridge && root.bridge.sheets) {
                                root.bridge.sheets.openHomeworkAt(day, start, end)
                            }
                        }
                        root.dragRangeActive = false
                        root.dragRangeValid = false
                        root.dragRangeCanceled = false
                        root.dragRangeStartMin = 0
                        root.dragRangeEndMin = 0
                        root.dragRangeDay = -1
                    }
                }
                onCentroidChanged: {
                    if (active && root.dragRangeActive && root.dragRangeValid && !root.dragRangeCanceled) {
                        var m1 = root.snapToQuarter(root.dragRangePressY)
                        var m2 = root.snapToQuarter(centroid.position.y)
                        root.dragRangeStartMin = Math.min(m1, m2)
                        root.dragRangeEndMin = Math.max(m1, m2)
                    }
                }
            }

            Rectangle {
                id: rangeGhost
                objectName: "rangeGhost"
                visible: root.dragRangeActive && (root.dragRangeEndMin > root.dragRangeStartMin) && !root.dragRangeCanceled
                x: root.gutter + root.dragRangeDay * root.dayWidth + 3
                y: (root.dragRangeStartMin / 60) * root.row
                width: Math.max(8, root.dayWidth - 6)
                height: Math.max(4, ((root.dragRangeEndMin - root.dragRangeStartMin) / 60) * root.row - 2)
                radius: 6
                color: m3.primaryContainer
                opacity: 0.7
                border.width: 2
                border.color: m3.primary
                z: 10
            }

            // Today's column is a step above the page, as in the mockup.
            Rectangle {
                objectName: "todayColumn"
                visible: !!bridge && bridge.nowDay >= 0 && bridge.nowDay < root.columns
                         && !(root.theme && root.theme.todayHighlight === false)
                x: root.gutter + (bridge ? bridge.nowDay : 0) * root.dayWidth
                width: root.dayWidth
                height: parent.height
                color: m3.surfaceContainerLow
            }

            Rectangle {
                objectName: "dropColumn"
                visible: root.dropDay >= 0
                x: root.gutter + Math.max(0, root.dropDay) * root.dayWidth
                width: root.dayWidth
                height: parent.height
                color: m3.secondaryContainer
                opacity: 0.6
            }

            Rectangle {
                objectName: "dropSlot"
                // Above the now line (z 1) and the blocks, so the slot's outline is never crossed.
                z: 4
                visible: root.dropDay >= 0
                x: root.gutter + Math.max(0, root.dropDay) * root.dayWidth + 3
                y: Math.max(0, root.dropHour) * root.row
                width: root.dayWidth - 6
                height: root.row - 2
                radius: 6
                color: "transparent"
                border.width: 2
                border.color: m3.primary
            }

            Repeater {
                model: 24

                Rectangle {
                    y: index * root.row
                    x: root.gutter
                    width: parent.width - root.gutter
                    height: 1
                    color: root.theme && root.theme.hourLines === "None" ? "transparent" : root.line
                }
            }

            Repeater {
                model: root.columns + 1

                Rectangle {
                    x: root.gutter + index * root.dayWidth
                    width: root.highContrast ? 1.5 : 1
                    height: parent.height
                    color: root.line
                }
            }

            Repeater {
                id: hourLabels
                objectName: "hourLabels"
                model: bridge ? bridge.hours : 0

                Text {
                    objectName: "hourLabel"
                    x: 0
                    y: Math.max(0, index * root.row - 8)
                    width: root.gutter - 8
                    horizontalAlignment: Text.AlignRight
                    text: model.label
                    color: m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 11 * root.typeScale
                    font.weight: 500
                }
            }

            Rectangle {
                objectName: "nowLine"
                visible: !!bridge && bridge.nowDay >= 0 && bridge.nowDay < root.columns
                x: root.gutter - 5
                y: (bridge ? bridge.nowMinute : 0) / 60 * root.row
                width: parent.width - root.gutter + 5
                height: 2
                color: root.now
                z: 1
            }

            Repeater {
                id: weekBlocks
                objectName: "weekBlocks"
                model: bridge ? bridge.blocks : 0

                WeekBlock {
                    id: blockCell
                    objectName: "weekBlock"
                    z: 2
                    passive: root.passive
                    x: root.gutter + model.day * root.dayWidth + 3
                    y: model.start / 60 * root.row
                    width: Math.max(8, root.dayWidth - 6)
                    height: Math.max(36, (model.end - model.start) / 60 * root.row - 2)
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    category: model.category
                    title: model.title
                    detail: {
                        var text = (root.theme && root.theme.showTimes === false) ? "" : model.detail
                        if (root.theme && root.theme.showLengths)
                            text = (text ? text + " · " : "") + (model.end - model.start) + "m"
                        return text
                    }
                    past: model.past
                    done: model.done
                    fresh: model.fresh
                    homework: model.homework
                    onToggled: if (root.bridge) root.bridge.week.toggleDone(model.assignmentId)
                    onOpened: if (root.bridge && root.bridge.sheets) root.bridge.sheets.editBlock(model.blockId, model.day)
                    onMenuAsked: (mx, my) => root.openBlockMenu(blockCell, model, mx, my)
                    onActiveFocusChanged: if (activeFocus) scroller.reveal(y, height)
                    onFocused: scroller.reveal(y, height)
                }
            }

            Rectangle {
                objectName: "nowDot"
                visible: !!bridge && bridge.nowDay >= 0 && bridge.nowDay < root.columns
                x: root.gutter - 5
                y: (bridge ? bridge.nowMinute : 0) / 60 * root.row - 4
                width: 10
                height: 10
                radius: 5
                color: root.now
                z: 3
            }
        }
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
            font.pixelSize: 13
            font.weight: 500
        }
    }

    property Item menuOriginItem: null
    property var menuTargetModel: null

    function openBlockMenu(item, blockModel, mx, my) {
        menuOriginItem = item
        menuTargetModel = {
            blockId: blockModel.blockId,
            assignmentId: blockModel.assignmentId,
            day: blockModel.day,
            done: blockModel.done
        }
        var mapped = item.mapToItem(root, mx, my)
        var menuX = Math.max(8, Math.min(mapped.x, root.width - blockMenu.width - 8))
        var menuY = Math.max(8, Math.min(mapped.y, root.height - blockMenu.height - 8))
        blockMenu.x = menuX
        blockMenu.y = menuY
        blockMenu.entries = [
            { label: "Edit", icon: "edit_note" },
            { label: blockModel.done ? "Open again" : "Mark finished", icon: "check" },
            { label: "Delete", icon: "close" }
        ]
        blockMenu.cursor = 0
        blockMenu.open = true
        blockMenu.forceActiveFocus()
    }

    function closeBlockMenu() {
        if (!blockMenu.open && !menuOriginItem && !menuTargetModel)
            return
        blockMenu.open = false
        var origin = menuOriginItem
        menuOriginItem = null
        menuTargetModel = null
        if (origin && origin.visible)
            origin.forceActiveFocus()
    }

    FocusScope {
        id: menuOverlay
        anchors.fill: parent
        z: 50
        visible: blockMenu.open
        enabled: blockMenu.open

        Rectangle {
            id: menuDim
            anchors.fill: parent
            color: "transparent"
            TapHandler {
                enabled: blockMenu.open
                onTapped: root.closeBlockMenu()
            }
        }

        Menu {
            id: blockMenu
            objectName: "blockMenu"
            open: false
            focus: true
            activeFocusOnTab: open && !root.passive
            onActiveFocusChanged: {
                if (!activeFocus && open)
                    root.closeBlockMenu()
            }
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            onChosen: (index, label) => {
                var target = root.menuTargetModel
                root.closeBlockMenu()
                if (!root.bridge || !target)
                    return
                if (label === "Edit") {
                    if (root.bridge.sheets)
                        root.bridge.sheets.editBlock(target.blockId, target.day)
                } else if (label === "Mark finished" || label === "Open again") {
                    root.bridge.week.toggleDone(target.assignmentId)
                } else if (label === "Delete") {
                    if (root.bridge.sheets) {
                        if (root.bridge.sheets.askDeleteHomework)
                            root.bridge.sheets.askDeleteHomework(target.assignmentId)
                        else
                            root.bridge.sheets.askDeleteUnfinished(target.assignmentId)
                    }
                }
            }
            onDismissed: root.closeBlockMenu()
        }
    }
}
