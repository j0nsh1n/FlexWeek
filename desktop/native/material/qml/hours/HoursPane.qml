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
    property int dropMinute: -1
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

    // A block held by the mouse: which, how (move, top, bottom), where it started, and where it would land.
    property var held: null
    property bool holdCanceled: false
    property var landing: null
    readonly property bool handing: held !== null
    readonly property bool canHand: !root.passive && !!root.bridge && !!root.bridge.week
                                    && !!root.bridge.week.moveBlock

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
    // Blocks that share time (Jonathan, 2026-11-08): each sits at its own time; a later one lies on the
    // earlier ones a step right. The step leaves the covered block's edge in sight, or, when its name
    // runs up that edge on its side, room for the name. Both grow with the text size.
    readonly property real overlapStep: M3Font.px(16)
    FontMetrics {
        id: nameFont
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        font.weight: 600
    }
    // The 4 px edge bar, the name's line on its side, and a margin each side of it.
    readonly property real sideStrip: 4 + 3 + Math.ceil(nameFont.height) + 3
    // The least height that shows a block's title line whole, as EventBlock lays it out.
    readonly property real nameRoom: ((root.theme && root.theme.cardPad !== undefined) ? root.theme.cardPad : 6)
                                     + Math.ceil(nameFont.height * 1.25) + (root.highContrast ? 2 : 1)
    readonly property var blockList: root.weekMode
                                     ? (root.bridge && root.bridge.blockRows ? root.bridge.blockRows : [])
                                     : (root.bridge && root.bridge.day && root.bridge.day.blockRows
                                        ? root.bridge.day.blockRows : [])
    readonly property var placement: root.placeBlocks(root.blockList, root.row, root.nameRoom,
                                                      root.overlapStep, root.sideStrip)

    // Where each block's words go and how far right it steps, by its place in the model. A block that
    // others lie on keeps its name where it shows: above them when they start a line or more later,
    // else below them when they end a line or more before it, else on its side up its uncovered strip.
    function placeBlocks(rows, row, room, step, side) {
        var n = rows ? rows.length : 0
        var top = [], bottom = [], coverTop = [], coverBottom = [], spots = []
        var i, k
        for (i = 0; i < n; i++) {
            top.push(rows[i].start / 60 * row)
            bottom.push(top[i] + Math.max(36, (rows[i].end - rows[i].start) / 60 * row - 2))
            coverTop.push(Infinity)
            coverBottom.push(-Infinity)
        }
        for (i = 0; i < n; i++) {
            var lies = rows[i].under || []
            for (k = 0; k < lies.length; k++) {
                coverTop[lies[k]] = Math.min(coverTop[lies[k]], top[i])
                coverBottom[lies[k]] = Math.max(coverBottom[lies[k]], bottom[i])
            }
        }
        for (i = 0; i < n; i++) {
            var spot = { offset: 0, side: false, wordsTop: 0, wordsRoom: -1 }
            if (coverTop[i] !== Infinity) {
                if (coverTop[i] - top[i] >= room) {
                    spot.wordsRoom = coverTop[i] - top[i]
                } else if (bottom[i] - coverBottom[i] >= room) {
                    spot.wordsTop = coverBottom[i] - top[i]
                    spot.wordsRoom = bottom[i] - coverBottom[i]
                } else {
                    spot.side = true
                }
            }
            var beneath = rows[i].under || []
            for (k = 0; k < beneath.length; k++) {
                var below = spots[beneath[k]]
                spot.offset = Math.max(spot.offset, below.offset + (below.side ? side : step))
            }
            spots.push(spot)
        }
        return spots
    }

    // The student's time step; a draw or click on empty time lands on its nearest mark.
    readonly property int dragStep: bridge && bridge.week && bridge.week.dragStep > 0 ? bridge.week.dragStep : 5

    function snapToQuarter(y) {
        var snapped = Math.round((y / root.row) * 60 / root.dragStep) * root.dragStep
        return Math.max(0, Math.min(24 * 60, snapped))
    }

    function snapQuarter(minute) {
        return Math.round(minute / 15) * 15
    }

    // The topmost block under a point of the grid, as the block its hold needs to know.
    function blockAt(x, y) {
        var found = null
        for (var i = 0; i < weekBlocks.count; i++) {
            var block = weekBlocks.itemAt(i)
            if (block && block.visible && x >= block.x && x <= block.x + block.width
                    && y >= block.y && y <= block.y + block.height && (!found || block.z >= found.z))
                found = block
        }
        return found
    }

    function startHand(block, x, y) {
        var edge = Math.min(8, block.height / 4)
        var how = y - block.y <= edge ? "top" : (block.y + block.height - y <= edge ? "bottom" : "move")
        root.holdCanceled = false
        root.held = { blockId: block.blockId, day: block.blockDay, start: block.blockStart, end: block.blockEnd,
                      how: how, pressY: y }
        root.landing = { day: block.blockDay, start: block.blockStart, end: block.blockEnd }
    }

    // Where the held block lands for a pointer at (x, y) on the grid: moved by the pointer's travel and
    // snapped to a quarter hour, or with one edge moved, never shorter than a quarter hour.
    function landingFor(x, y) {
        var held = root.held
        var travel = (y - held.pressY) / root.row * 60
        var day = held.day
        var start = held.start
        var end = held.end
        if (held.how === "move") {
            var length = held.end - held.start
            start = Math.max(0, Math.min(24 * 60 - length, root.snapQuarter(held.start + travel)))
            end = start + length
            if (root.weekMode)
                day = Math.max(0, Math.min(root.columns - 1, Math.floor((x - root.gutter) / root.dayWidth)))
        } else if (held.how === "top") {
            start = Math.max(0, Math.min(held.end - 15, root.snapQuarter(held.start + travel)))
        } else {
            end = Math.min(24 * 60, Math.max(held.start + 15, root.snapQuarter(held.end + travel)))
        }
        return { day: day, start: start, end: end }
    }

    function moveHand(x, y) {
        if (root.held && !root.holdCanceled)
            root.landing = root.landingFor(x, y)
    }

    function cancelHand() {
        root.holdCanceled = true
        root.landing = null
    }

    function dropHand() {
        var held = root.held
        var landing = root.landing
        var canceled = root.holdCanceled
        root.held = null
        root.landing = null
        root.holdCanceled = false
        if (!held || canceled || !landing)
            return
        if (landing.day === held.day && landing.start === held.start && landing.end === held.end)
            return
        root.bridge.week.moveBlock(held.blockId, held.day, landing.day, landing.start, landing.end)
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
    // Today was pressed: show the line once this week has it, however the grid was scrolled before.
    property bool nowAsked: false

    function revealNow() {
        if (!root.followNow || scroller.moving || scroller.dragging || root.zooming)
            return
        if (root.host && root.host.holding)
            return
        var view = scroller.height
        if (!bridge || view < 40 || bridge.nowDay < 0)
            return
        var key = bridge.nowDay + ":" + (bridge.week ? bridge.week.columns : 7) + ":" + root.typeScale + ":" + root.density
        if (revealedKey === key && !nowAsked)
            return
        revealedKey = key
        nowAsked = false
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
        // A block that is on at the opening minute shows its top, its done circle and its start label too:
        // when its top would be cut, or the hour label at its start would sit under the zoom buttons, the
        // pane opens `above` higher than the block instead. A block that began so long ago that this would
        // push the opening minute out of the pane's top 60 % leaves now where the rule puts it.
        var blocks = root.blockList || []
        var clear = zoomPill.visible ? zoomPill.y + zoomPill.height + 4 : 0
        for (var i = 0; i < blocks.length; i++) {
            var from = blocks[i].start
            if (from >= root.openingMinute || blocks[i].end <= root.openingMinute)
                continue
            var blockTop = from / 60 * root.row
            var top = Math.max(0, blockTop - above)
            var labelHidden = from % 60 === 0 && blockTop - wanted < clear
            if ((blockTop < wanted || labelHidden) && top < wanted && y - top <= view * 0.6)
                wanted = top
        }
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
        // A mouse press-and-drag must not pan the grid: it is drag-to-create's. The wheel, a touchpad, the
        // scroll bar, the keys and a touchscreen still scroll it.
        acceptedButtons: Qt.NoButton

        // The student's own scrolling ends a pending Today: the grid does not chase the line afterwards.
        onMovingChanged: if (moving) root.nowAsked = false

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
            target: root.followNow && root.bridge ? root.bridge.week : null
            function onTodayAsked() {
                root.nowAsked = true
                root.revealNow()
            }
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
                // A block held by the mouse goes back: nothing is saved when the button is let go. The
                // shell's own Esc waits while a block is held, so the key reaches here.
                if (root.handing) {
                    root.cancelHand()
                    event.accepted = true
                } else if (root.rangeHost.dragRangeActive) {
                    root.rangeHost.cancelDragRange()
                    event.accepted = true
                }
            }

            // A click on free time offers to add something there: an hour from the nearest mark of the
            // student's time step, as the Widgets grid places a click.
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
                    if (!active && root.held) {
                        root.dropHand()
                        return
                    }
                    if (active) {
                        var px = centroid.pressPosition.x
                        var py = centroid.pressPosition.y
                        var under = root.canHand ? root.blockAt(px, py) : null
                        if (under) {
                            range.dragRangeValid = false
                            range.dragRangeActive = false
                            root.startHand(under, px, py)
                            // The block takes the keyboard focus, so Esc reaches the grid; the grid does not
                            // scroll to it while it is held.
                            under.forceActiveFocus()
                            root.moveHand(centroid.position.x, centroid.position.y)
                            return
                        }
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
                            // One step is the shortest block, as in the Widgets grid.
                            if (end - start >= root.dragStep)
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
                    if (active && root.held) {
                        root.moveHand(centroid.position.x, centroid.position.y)
                        return
                    }
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

            // Where the held block would land, while it is held.
            Rectangle {
                objectName: "handGhost"
                visible: root.handing && !!root.landing
                z: 10
                x: root.weekMode ? root.gutter + (root.landing ? root.landing.day : 0) * root.dayWidth + 3
                                 : root.gutter + 3
                y: (root.landing ? root.landing.start : 0) / 60 * root.row
                width: root.weekMode ? Math.max(8, root.dayWidth - 6)
                                     : Math.max(8, hours.width - root.gutter - 3 - root.blockRightInset)
                height: Math.max(4, ((root.landing ? root.landing.end - root.landing.start : 0) / 60) * root.row - 2)
                radius: 6
                color: m3.primaryContainer
                opacity: 0.7
                border.width: 2
                border.color: m3.primary
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
                z: 6
                visible: root.weekMode && root.dropDay >= 0
                x: root.gutter + Math.max(0, root.dropDay) * root.dayWidth + 3
                y: Math.max(0, root.dropMinute) / 60 * root.row
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
                    // The time label is drawn over an hour number it lands on; the number goes so the two
                    // are never read together.
                    readonly property bool underNowLabel: nowLabel.visible && y < nowLabel.y + nowLabel.height
                                                          && y + height > nowLabel.y
                    // Whole or not at all: hide a label cut by the pane's top edge or covered by the zoom pill.
                    opacity: viewY >= 0 && !underNowLabel
                             && !(zoomPill.visible && viewY < zoomPill.y + zoomPill.height + 2
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

            // Today's column only, over every block (Jonathan, 2026-11-10): Day has the one column.
            Rectangle {
                id: nowLine
                objectName: "nowLine"
                visible: root.showNowLine
                x: root.gutter + (root.weekMode && bridge ? Math.max(0, bridge.nowDay) : 0) * root.dayWidth
                y: (bridge ? bridge.nowMinute : 0) / 60 * root.row
                width: root.weekMode ? root.dayWidth : parent.width - root.gutter
                height: 2
                color: root.now
                z: 4
            }

            // The time now, in the hour column at the line's height. It lives in the column, so it never
            // covers a block; an hour number it lands on is hidden (see hourLabel).
            Rectangle {
                id: nowLabel
                objectName: "nowLabel"
                readonly property string time: (root.bridge && root.bridge.clockText) ? root.bridge.clockText : ""
                visible: root.showNowLine && !root.passive && time !== ""
                width: Math.min(root.gutter - 8, nowLabelText.implicitWidth + 12)
                height: Math.ceil(nowLabelText.implicitHeight) + 6
                x: root.gutter - 6 - width
                y: (root.bridge ? root.bridge.nowMinute : 0) / 60 * root.row + nowLine.height / 2 - height / 2
                radius: 4
                color: root.now
                z: 7
                Accessible.role: Accessible.StaticText
                Accessible.name: "Current time, " + nowLabel.time
                Text {
                    id: nowLabelText
                    objectName: "nowLabelText"
                    anchors.centerIn: parent
                    text: nowLabel.time
                    color: m3.inkError
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(11)
                    font.weight: 600
                }
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
                    // Model order is time order, so a later block lies on the earlier ones it shares time
                    // with; a focused block comes to the front so its focus ring shows whole.
                    z: activeFocus || keyFocus ? 3 : 2
                    passive: root.passive
                    dayOpen: !root.weekMode
                    // Blocks sharing time overlap (Jonathan, 2026-11-08): the earliest keeps the whole lane,
                    // each later one sits a step right, all at their own time. A deep stack stops at the
                    // lane's right edge rather than run into the next day.
                    readonly property real laneSpan: root.weekMode
                                                     ? root.dayWidth - 6
                                                     : hours.width - root.gutter - 3 - root.blockRightInset
                    readonly property var spot: root.placement.length === weekBlocks.count
                                                ? root.placement[index] : null
                    readonly property real indentX: Math.max(0, Math.min(
                        spot ? spot.offset : (model.indent || 0) * root.overlapStep, laneSpan - 8))
                    raised: (model.indent || 0) > 0
                    nameSide: !!spot && spot.side
                    sideStrip: root.sideStrip
                    wordsTop: spot ? spot.wordsTop : 0
                    wordsRoom: spot ? spot.wordsRoom : -1
                    x: (root.weekMode ? root.gutter + model.day * root.dayWidth + 3 : root.gutter + 3) + indentX
                    y: model.start / 60 * root.row
                    width: Math.max(8, laneSpan - indentX)
                    height: Math.max(36, (model.end - model.start) / 60 * root.row - 2)
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    blockId: model.blockId
                    blockDay: model.day
                    blockStart: model.start
                    blockEnd: model.end
                    category: model.category
                    title: model.title
                    detail: blockCell.timeLine(model.detail)
                    detailStart: blockCell.timeLine(model.detailStart)
                    function timeLine(time) {
                        var text = (root.theme && root.theme.showTimes === false) ? "" : time
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
                        start: model.start,
                        end: model.end,
                        done: model.done,
                        homework: model.homework
                    }, mx, my)
                    onActiveFocusChanged: if (activeFocus && !root.handing) root.reveal(y, height)
                    onFocused: if (!root.handing) root.reveal(y, height)
                }
            }

            Rectangle {
                objectName: "nowDot"
                visible: root.showNowLine
                x: nowLine.x - 5
                y: (bridge ? bridge.nowMinute : 0) / 60 * root.row - 4
                width: 10
                height: 10
                radius: 5
                color: root.now
                z: 5
            }
        }
    }

    property Item menuOriginItem: null
    property var menuTargetModel: null
    // "block": the block's own items. "days": Move to day...'s list of the week's days.
    property string menuMode: "block"

    function blockEntries(target) {
        var rows = [
            { label: "Edit", icon: "edit_note" },
            { label: "Duplicate", icon: "add" },
            { label: "Move to day...", icon: "calendar_view_week" },
            { label: "Copy", icon: "content_copy" }
        ]
        // A fixed time has nothing to finish.
        if (target.homework)
            rows.push({ label: target.done ? "Open again" : "Mark finished", icon: "check" })
        rows.push({ label: "Delete", icon: "close" })
        return rows
    }

    // A new list of rows changes the menu's height: keep it whole inside the pane.
    function fitMenu() {
        blockMenu.y = Math.max(8, Math.min(blockMenu.y, root.height - blockMenu.height - 8))
    }

    // The week's days as the headers name them, today marked as a header's reader hears it.
    function dayEntries() {
        var days = (root.bridge && root.bridge.week && root.bridge.week.dayRows) ? root.bridge.week.dayRows : []
        var rows = []
        for (var i = 0; i < days.length; i++)
            rows.push({ label: days[i].label + (days[i].today ? ", today" : ""), icon: "" })
        return rows
    }

    function openBlockMenu(item, blockModel, mx, my) {
        menuOriginItem = item
        menuTargetModel = {
            blockId: blockModel.blockId,
            assignmentId: blockModel.assignmentId,
            day: blockModel.day,
            start: blockModel.start,
            end: blockModel.end,
            done: blockModel.done,
            homework: blockModel.homework
        }
        menuMode = "block"
        blockMenu.entries = blockEntries(menuTargetModel)
        // Placed after the rows are in: the menu's height is its rows, so earlier it was 16 px and the
        // first menu near the bottom ran off the window.
        var mapped = item.mapToItem(root, mx, my)
        blockMenu.x = Math.max(8, Math.min(mapped.x, root.width - blockMenu.width - 8))
        blockMenu.y = Math.max(8, Math.min(mapped.y, root.height - blockMenu.height - 8))
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
        var entries = [{ label: "Add fixed time here", icon: "schedule" }]
        // Homework is planned in quarter hours, so a shorter range offers fixed time only.
        if (end - start >= 15)
            entries.unshift({ label: "Add homework here", icon: "edit_note" })
        blockMenu.entries = entries
        blockMenu.x = Math.max(8, Math.min(mapped.x, root.width - blockMenu.width - 8))
        blockMenu.y = Math.max(8, Math.min(mapped.y, root.height - blockMenu.height - 8))
        blockMenu.cursor = 0
        blockMenu.open = true
        blockMenu.forceActiveFocus()
    }

    function closeBlockMenu(giveFocusBack) {
        slotDay = -1
        menuMode = "block"
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
            // Takes the tap, so a click outside the menu only closes it: the block under it does not open.
            TapHandler {
                enabled: blockMenu.open
                gesturePolicy: TapHandler.WithinBounds
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
                if (target && !target.slot && root.menuMode === "block" && label === "Move to day...") {
                    // A second list in the same menu: the week's days, Esc back to the block's items.
                    root.menuMode = "days"
                    blockMenu.entries = root.dayEntries()
                    root.fitMenu()
                    blockMenu.cursor = Math.max(0, Math.min(target.day, blockMenu.entries.length - 1))
                    return
                }
                if (target && !target.slot && root.menuMode === "days") {
                    root.closeBlockMenu()
                    if (root.bridge && root.bridge.week && index !== target.day)
                        root.bridge.week.moveBlock(target.blockId, target.day, index, target.start, target.end)
                    return
                }
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
                } else if (label === "Duplicate") {
                    if (root.bridge.week)
                        root.bridge.week.duplicateBlock(target.blockId, target.day)
                } else if (label === "Copy") {
                    if (root.bridge.week)
                        root.bridge.week.copyBlock(target.blockId, target.day)
                } else if (label === "Mark finished" || label === "Open again") {
                    if (root.bridge.week)
                        root.bridge.week.toggleDone(target.assignmentId)
                } else if (label === "Delete") {
                    if (root.bridge.sheets) {
                        if (!target.homework)
                            root.bridge.sheets.askDeleteBlock(target.blockId, target.day)
                        else if (root.bridge.sheets.askDeleteHomework)
                            root.bridge.sheets.askDeleteHomework(target.assignmentId)
                        else
                            root.bridge.sheets.askDeleteUnfinished(target.assignmentId)
                    }
                }
            }
            onDismissed: {
                if (root.menuMode === "days" && root.menuTargetModel) {
                    // Esc in the days list goes back to the block's own items.
                    root.menuMode = "block"
                    blockMenu.entries = root.blockEntries(root.menuTargetModel)
                    root.fitMenu()
                    blockMenu.cursor = 0
                    blockMenu.open = true
                    blockMenu.forceActiveFocus()
                    return
                }
                root.closeBlockMenu()
            }
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
