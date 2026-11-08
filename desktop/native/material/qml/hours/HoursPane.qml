import QtQuick
import QtQuick.Controls
import components 1.0
import "../week"

Item {
    id: root
    // A block's menu is open: the zoom keys leave the hours behind it alone (J21).
    readonly property bool menuOpen: blockMenu.open
    property var bridge
    property var theme: ({})
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool passive: false
    property bool phone: false
    property int row: 56
    property int gutter: hourGutter
    property int columns: 1
    property real dayWidth: Math.max(48, (width - gutter) / Math.max(1, columns))
    property int filterDay: -1
    property bool showNowLine: false
    property bool showPill: false
    property bool weekMode: false
    property bool followNow: false
    property bool followOpening: false
    property int openingMinute: 8 * 60
    property int scrollClearance: 0
    property string scrollerName: "weekScroller"
    property var host: null

    property int dropDay: -1
    property int dropHour: -1
    property int dragRangeDay: -1
    property int dragRangeStartMin: 0
    property int dragRangeEndMin: 0
    property bool dragRangeActive: false
    property bool dragRangeValid: false
    property bool dragRangeCanceled: false
    property real dragRangePressY: 0
    // Week keeps the drag range on its view (Esc and the header read it); Day keeps it here.
    readonly property var rangeHost: root.host ? root.host : root
    readonly property bool takesEmptyTime: !root.passive && (root.weekMode ? !!root.host : root.filterDay >= 0)
    // The time the empty-time menu was opened for, marked on the grid while the menu is up.
    property int slotDay: -1
    property int slotStart: 0
    property int slotEnd: 0

    property alias scroller: scroller
    property alias hours: hours
    property int wheelAcc: 0
    property bool zooming: false

    readonly property real typeScale: (theme && theme.typeScale) ? theme.typeScale : 1
    // The hour column is as wide as its widest label at this text size, as the Widgets grid's
    // hour_gutter is, and never under the 68 px the layout was drawn for.
    FontMetrics {
        id: hourFont
        font.family: M3Font.family
        font.pixelSize: M3Font.px(11)
        font.weight: 500
    }
    readonly property int hourGutter: {
        var labels = (root.bridge && root.bridge.hourLabels) ? root.bridge.hourLabels : ["10:00 AM", "12:00 PM"]
        var widest = 0
        for (var i = 0; i < labels.length; i++)
            widest = Math.max(widest, hourFont.advanceWidth(labels[i]))
        return Math.max(68, Math.ceil(widest) + 8 + 6)
    }
    // A new text size or density moves the time now on the grid, so the week shows it again.
    onTypeScaleChanged: if (root.followNow) Qt.callLater(root.revealNow)
    onDensityChanged: if (root.followNow) Qt.callLater(root.revealNow)
    readonly property int blockRightInset: root.weekMode ? 3 : 16

    function snapToQuarter(y) {
        var snapped = Math.round((y / root.row) * 60 / 15) * 15
        return Math.max(0, Math.min(24 * 60, snapped))
    }

    function dayAt(x) {
        return root.weekMode ? Math.floor((x - root.gutter) / root.dayWidth) : root.filterDay
    }

    // Day's own test for a point on free time: inside the hours and on no block.
    function emptyGridTimeAt(x, y) {
        if (root.filterDay < 0 || x < root.gutter || x >= hours.width || y < 0 || y >= 24 * root.row)
            return false
        for (var i = 0; i < weekBlocks.count; i++) {
            var block = weekBlocks.itemAt(i)
            if (block && x >= block.x && x <= block.x + block.width && y >= block.y && y <= block.y + block.height)
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

    function openingAbove(view) {
        var margin = 45 / 60 * root.row
        if (view < margin + root.row)
            return Math.min(margin, Math.max(8, view * 0.08))
        return margin
    }

    M3Palette { id: m3; theme: root.theme }
    readonly property var line: theme && theme.hourLines === "Clear" ? m3.outline : m3.outlineVariant
    readonly property var now: (theme && theme.nowLine) ? theme.nowLine : m3.error

    function zoomAbout(steps, viewY) {
        if (root.passive || !bridge || !bridge.zoomBy)
            return
        var row = Math.max(1, root.row)
        // The anchor is a time in the day: the hours end at midnight, and Day's pane scrolls on past
        // it so an evening can open near the top.
        var minute = Math.min(24 * 60, ((scroller.contentY + viewY) / row) * 60)
        viewY = (minute / 60) * row - scroller.contentY
        root.zooming = true
        if (steps === 0)
            bridge.zoomReset()
        else
            bridge.zoomBy(steps)
        function place() {
            var next = Math.max(1, root.row)
            var y = (minute / 60) * next - viewY
            // A zoom never leaves midnight above the bottom of the view while earlier time could show.
            var dayEnd = Math.max(0, 24 * next - scroller.height)
            var limit = Math.min(Math.max(0, scroller.contentHeight - scroller.height), dayEnd)
            scroller.contentY = Math.min(Math.max(0, y), limit)
            root.zooming = false
        }
        place()
        Qt.callLater(place)
    }

    // Keys and the pill zoom about the middle of the hours on screen, not of blank space past midnight.
    function middleOfHours() {
        var shown = Math.min(scroller.height, Math.max(0, 24 * root.row - scroller.contentY))
        return shown / 2
    }

    function zoomFromKeys(steps) {
        zoomAbout(steps, middleOfHours())
    }

    function resetZoomFromKeys() {
        zoomAbout(0, middleOfHours())
    }

    function reveal(itemY, itemHeight) {
        if (itemY < scroller.contentY)
            scroller.contentY = Math.max(0, itemY - 8)
        else if (itemY + itemHeight > scroller.contentY + scroller.height)
            scroller.contentY = Math.min(Math.max(0, scroller.contentHeight - scroller.height), itemY + itemHeight - scroller.height + 8)
    }

    property string revealedKey: ""

    function revealNow() {
        if (!root.followNow || scroller.moving || scroller.dragging || root.zooming)
            return
        if (root.host && root.host.holding)
            return
        var view = scroller.height
        if (!bridge || view < 40 || bridge.nowDay < 0)
            return
        var key = bridge.nowDay + ":" + (bridge.week ? bridge.week.columns : 7) + ":" + root.typeScale + ":" + root.density
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
        var limit = Math.max(0, scroller.contentHeight - view)
        scroller.contentY = Math.min(Math.max(0, contentY), limit)
    }

    property string openedKey: ""
    // Iso is the date. A clock tick, save, or zoom leaves it alone; previous/next/Today change it.
    readonly property string dateKey: (root.followOpening && root.bridge && root.bridge.day)
                                      ? root.bridge.day.iso : ""
    onDateKeyChanged: if (root.followOpening) root.revealOpening(true)
    // A turn later, so the opening minute that arrives with the same week has landed too.
    onFilterDayChanged: if (root.followOpening && root.filterDay >= 0 && openedKey === "") Qt.callLater(root.revealOpening, false)

    function revealOpening(force) {
        if (!root.followOpening)
            return
        if (!force && (scroller.moving || scroller.dragging || root.zooming))
            return
        var view = scroller.height
        if (view < 40)
            return
        var key = (bridge && bridge.day ? bridge.day.iso : "")
        if (!force && openedKey === key)
            return
        // A date in a week still loading has no blocks yet and opens at the fallback hour; it stays
        // unopened so the opening runs again once the week lands (filterDay becomes valid).
        openedKey = root.filterDay >= 0 ? key : ""
        var y = (root.openingMinute / 60) * root.row
        var above = openingAbove(view)
        var wanted = Math.max(0, y - above)
        var limit = Math.max(0, scroller.contentHeight - view)
        scroller.contentY = Math.min(wanted, limit)
    }

    Connections {
        target: root.followOpening && root.bridge && root.bridge.day ? root.bridge.day : null
        function onDateOpened() {
            root.revealOpening(true)
        }
    }

    ZoomPill {
        id: zoomPill
        visible: root.showPill && !root.phone && !root.passive
        z: 6
        x: Math.round((root.gutter - width) / 2)
        y: 8
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        canZoomIn: !!(bridge && bridge.canZoomIn)
        canZoomOut: !!(bridge && bridge.canZoomOut)
        onZoomOut: root.zoomFromKeys(-1)
        onZoomIn: root.zoomFromKeys(1)
    }

    Flickable {
        id: scroller
        objectName: root.scrollerName
        anchors.fill: parent
        contentWidth: width
        contentHeight: hours.height + root.scrollClearance
                       + (root.followOpening ? Math.max(0, height - openingAbove(height)) : 0)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        onHeightChanged: {
            if (root.followNow)
                root.revealNow()
            if (root.followOpening)
                root.revealOpening(false)
        }
        onContentHeightChanged: {
            if (root.followOpening)
                root.revealOpening(false)
        }

        Connections {
            target: root.bridge
            function onBlocksChanged() {
                if (root.followNow)
                    root.revealNow()
            }
            function onChanged() {
                if (root.followNow)
                    root.revealNow()
            }
        }

        WheelHandler {
            acceptedModifiers: Qt.ControlModifier
            onWheel: (event) => {
                if (root.passive || !root.bridge || !root.bridge.zoomBy)
                    return
                root.wheelAcc += event.angleDelta.y
                var steps = Math.trunc(root.wheelAcc / 120)
                event.accepted = true
                if (steps === 0)
                    return
                root.wheelAcc -= steps * 120
                root.zoomAbout(steps, event.y - scroller.contentY)
            }
        }

        Item {
            id: hours
            width: scroller.width
            height: 24 * root.row
            focus: true
            Keys.onEscapePressed: (event) => {
                if (root.rangeHost.dragRangeActive) {
                    root.rangeHost.cancelDragRange()
                    event.accepted = true
                }
            }

            // A click on free time offers to add something there: an hour from the nearest quarter hour,
            // as the Widgets grid places a click.
            TapHandler {
                objectName: "emptyTimeTap"
                enabled: root.takesEmptyTime
                acceptedButtons: Qt.LeftButton
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onTapped: (eventPoint) => {
                    var p = eventPoint.position
                    if (!root.rangeHost.emptyGridTimeAt(p.x, p.y))
                        return
                    var start = Math.min(23 * 60, root.rangeHost.snapToQuarter(p.y))
                    root.openSlotMenu(root.dayAt(p.x), start, Math.min(24 * 60, start + 60), p.x, p.y)
                }
            }

            DragHandler {
                id: gridDrag
                target: null
                enabled: root.takesEmptyTime
                dragThreshold: 4
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                grabPermissions: PointerHandler.CanTakeOverFromItems | PointerHandler.CanTakeOverFromHandlersOfDifferentType
                onActiveChanged: {
                    var range = root.rangeHost
                    if (active) {
                        var px = centroid.pressPosition.x
                        var py = centroid.pressPosition.y
                        if (!range.emptyGridTimeAt(px, py)) {
                            range.dragRangeValid = false
                            range.dragRangeActive = false
                            return
                        }
                        hours.forceActiveFocus()
                        range.dragRangeValid = true
                        range.dragRangeCanceled = false
                        range.dragRangeDay = root.dayAt(px)
                        range.dragRangePressY = py
                        var m1 = range.snapToQuarter(py)
                        var m2 = range.snapToQuarter(centroid.position.y)
                        range.dragRangeStartMin = Math.min(m1, m2)
                        range.dragRangeEndMin = Math.max(m1, m2)
                        range.dragRangeActive = true
                        if (root.bridge && root.bridge.sheets)
                            root.bridge.sheets.setDragRangeActive(true)
                    } else {
                        if (root.bridge && root.bridge.sheets)
                            root.bridge.sheets.setDragRangeActive(false)
                        if (range.dragRangeActive && range.dragRangeValid && !range.dragRangeCanceled) {
                            var start = range.dragRangeStartMin
                            var end = range.dragRangeEndMin
                            var day = range.dragRangeDay
                            range.dragRangeActive = false
                            range.dragRangeValid = false
                            var menuX = centroid.pressPosition.x
                            // After the release is delivered, so the menu keeps the focus it takes.
                            if (end - start >= 15)
                                Qt.callLater(root.openSlotMenu, day, start, end, menuX, end / 60 * root.row)
                        }
                        range.dragRangeActive = false
                        range.dragRangeValid = false
                        range.dragRangeCanceled = false
                        range.dragRangeStartMin = 0
                        range.dragRangeEndMin = 0
                        range.dragRangeDay = -1
                    }
                }
                onCentroidChanged: {
                    var range = root.rangeHost
                    if (active && range.dragRangeActive && range.dragRangeValid && !range.dragRangeCanceled) {
                        var m1 = range.snapToQuarter(range.dragRangePressY)
                        var m2 = range.snapToQuarter(centroid.position.y)
                        range.dragRangeStartMin = Math.min(m1, m2)
                        range.dragRangeEndMin = Math.max(m1, m2)
                    }
                }
            }

            Rectangle {
                objectName: "rangeGhost"
                readonly property bool dragging: root.rangeHost.dragRangeActive
                                                 && root.rangeHost.dragRangeEndMin > root.rangeHost.dragRangeStartMin
                                                 && !root.rangeHost.dragRangeCanceled
                readonly property bool picked: blockMenu.open && root.slotDay >= 0
                readonly property int ghostDay: dragging ? root.rangeHost.dragRangeDay : root.slotDay
                readonly property int ghostStart: dragging ? root.rangeHost.dragRangeStartMin : root.slotStart
                readonly property int ghostEnd: dragging ? root.rangeHost.dragRangeEndMin : root.slotEnd
                visible: dragging || picked
                x: root.weekMode ? root.gutter + Math.max(0, ghostDay) * root.dayWidth + 3 : root.gutter + 3
                y: (ghostStart / 60) * root.row
                width: root.weekMode
                       ? Math.max(8, root.dayWidth - 6)
                       : Math.max(8, hours.width - root.gutter - 3 - root.blockRightInset)
                height: Math.max(4, ((ghostEnd - ghostStart) / 60) * root.row - 2)
                radius: 6
                color: m3.primaryContainer
                opacity: 0.7
                border.width: 2
                border.color: m3.primary
                z: 10
            }

            Rectangle {
                objectName: "todayColumn"
                visible: root.weekMode && !!bridge && bridge.nowDay >= 0 && bridge.nowDay < root.columns
                         && !(root.theme && root.theme.todayHighlight === false)
                x: root.gutter + (bridge ? bridge.nowDay : 0) * root.dayWidth
                width: root.dayWidth
                height: parent.height
                color: m3.surfaceContainerLow
            }

            Rectangle {
                objectName: "dropColumn"
                visible: root.weekMode && root.dropDay >= 0
                x: root.gutter + Math.max(0, root.dropDay) * root.dayWidth
                width: root.dayWidth
                height: parent.height
                color: m3.secondaryContainer
                opacity: 0.6
            }

            Rectangle {
                objectName: "dropSlot"
                z: 4
                visible: root.weekMode && root.dropDay >= 0
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
                model: root.weekMode ? root.columns + 1 : 0

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
                    readonly property real viewY: y - scroller.contentY
                    // Whole or not at all: hide a label cut by the pane's top edge or covered by the zoom pill.
                    opacity: viewY >= 0 && !(zoomPill.visible && viewY < zoomPill.y + zoomPill.height + 2
                                             && viewY + height > zoomPill.y - 2) ? 1 : 0
                    width: root.gutter - 8
                    horizontalAlignment: Text.AlignRight
                    text: model.label
                    color: m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(11)
                    font.weight: 500
                }
            }

            Rectangle {
                objectName: "nowLine"
                visible: root.showNowLine
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
                model: root.weekMode
                       ? (root.bridge ? root.bridge.blocks : 0)
                       : (root.bridge && root.bridge.day ? root.bridge.day.blocks : 0)

                WeekBlock {
                    id: blockCell
                    objectName: "weekBlock"
                    z: 2
                    passive: root.passive
                    dayOpen: !root.weekMode
                    // Blocks sharing time split their day's lane side by side (spec: overlaps are drawn
                    // side by side). A preview model without the roles keeps the whole lane.
                    readonly property int lanes: Math.max(1, model.columns || 1)
                    readonly property real laneSpan: root.weekMode
                                                     ? root.dayWidth - 6
                                                     : hours.width - root.gutter - 3 - root.blockRightInset
                    readonly property real laneStep: (laneSpan + 3) / lanes
                    x: (root.weekMode ? root.gutter + model.day * root.dayWidth + 3 : root.gutter + 3)
                       + (model.column || 0) * laneStep
                    y: model.start / 60 * root.row
                    width: Math.max(8, laneStep - 3)
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
                    onToggled: if (root.bridge && root.bridge.week) root.bridge.week.toggleDone(model.assignmentId)
                    onOpened: if (root.bridge && root.bridge.sheets) root.bridge.sheets.editBlock(model.blockId, model.day)
                    onMenuAsked: (mx, my) => root.openBlockMenu(blockCell, {
                        blockId: model.blockId,
                        assignmentId: model.assignmentId,
                        day: model.day,
                        done: model.done
                    }, mx, my)
                    onActiveFocusChanged: if (activeFocus) root.reveal(y, height)
                    onFocused: root.reveal(y, height)
                }
            }

            Rectangle {
                objectName: "nowDot"
                visible: root.showNowLine
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

    // Free time clicked or dragged over: add homework or a fixed time there (Jonathan, 2026-11-07).
    function openSlotMenu(day, start, end, hx, hy) {
        if (day < 0)
            return
        slotDay = day
        slotStart = start
        slotEnd = end
        menuOriginItem = hours
        menuTargetModel = { slot: true, day: day, start: start, end: end }
        var mapped = hours.mapToItem(root, hx, hy)
        blockMenu.entries = [
            { label: "Add homework here", icon: "edit_note" },
            { label: "Add fixed time here", icon: "schedule" }
        ]
        blockMenu.x = Math.max(8, Math.min(mapped.x, root.width - blockMenu.width - 8))
        blockMenu.y = Math.max(8, Math.min(mapped.y, root.height - blockMenu.height - 8))
        blockMenu.cursor = 0
        blockMenu.open = true
        blockMenu.forceActiveFocus()
    }

    function closeBlockMenu(giveFocusBack) {
        slotDay = -1
        if (!blockMenu.open && !menuOriginItem && !menuTargetModel)
            return
        blockMenu.open = false
        var origin = menuOriginItem
        menuOriginItem = null
        menuTargetModel = null
        if (giveFocusBack !== false && origin && origin.visible)
            origin.forceActiveFocus()
    }

    // The focus left the menu for an item outside it, such as a card the student clicked.
    function focusTakenElsewhere(item) {
        for (var at = item; at; at = at.parent) {
            if (at === menuOverlay)
                return false
        }
        return !!item
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
                    root.closeBlockMenu(!root.focusTakenElsewhere(Window.activeFocusItem))
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
                if (target.slot) {
                    if (!root.bridge.sheets)
                        return
                    if (label === "Add homework here")
                        root.bridge.sheets.openHomeworkAt(target.day, target.start, target.end)
                    else if (label === "Add fixed time here")
                        root.bridge.sheets.openBlockAt(target.day, target.start, target.end)
                } else if (label === "Edit") {
                    if (root.bridge.sheets)
                        root.bridge.sheets.editBlock(target.blockId, target.day)
                } else if (label === "Mark finished" || label === "Open again") {
                    if (root.bridge.week)
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

    Connections {
        target: !root.host && root.bridge && root.bridge.sheets ? root.bridge.sheets : null
        function onDragRangeCanceled() {
            root.cancelDragRange()
        }
    }

    Component.onCompleted: {
        if (root.followOpening)
            Qt.callLater(function() {
                if (typeof root.revealOpening === "function")
                    root.revealOpening(true)
            })
        if (root.followNow)
            Qt.callLater(function() {
                if (typeof root.revealNow === "function")
                    root.revealNow()
            })
    }
}
