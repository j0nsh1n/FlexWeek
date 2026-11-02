import QtQuick
import components 1.0

Item {
    id: root
    objectName: "materialWeek"
    property var bridge
    property bool phone: false
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // The floating add button sits 96px up on a phone. The grid can scroll clear of it.
    readonly property int scrollClearance: phone ? 96 : 0
    readonly property real gridWidth: phone ? width : Math.max(0, width - 320)
    readonly property real dayWidth: Math.max(48, (gridWidth - 64) / 7)
    // The shell clears `bridge` while the page is torn down. These stay readable then.
    readonly property int row: bridge ? bridge.hourRow : 56
    readonly property var ink: theme && theme.onSurface ? theme.onSurface : "#1a1c20"
    readonly property var line: theme && theme.outlineVariant ? theme.outlineVariant : "#c4c6d0"
    readonly property var now: theme && theme.primary ? theme.primary : "#425e91"
    readonly property var drawerFill: theme && theme.surfaceContainerLow ? theme.surfaceContainerLow : "#f3f3fa"

    Item {
        id: headerRow
        anchors.left: parent.left
        anchors.right: root.phone ? parent.right : drawer.left
        anchors.top: parent.top
        height: 36

        Repeater {
            id: dayHeaders
            objectName: "dayHeaders"
            model: bridge ? bridge.days : 0

            Text {
                objectName: "dayHeader"
                x: 64 + index * root.dayWidth
                width: root.dayWidth
                height: 36
                text: model.label
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: root.ink
                font.family: "Roboto Flex"
                font.pixelSize: 12
                font.weight: 600
            }
        }
    }

    Flickable {
        id: scroller
        anchors.left: parent.left
        anchors.right: root.phone ? parent.right : drawer.left
        anchors.top: headerRow.bottom
        anchors.bottom: root.phone ? drawer.top : parent.bottom
        contentWidth: width
        contentHeight: hours.height + root.scrollClearance
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        function revealNow() {
            var view = height
            if (!bridge || view < 40 || bridge.nowDay < 0)
                return
            var row = root.row
            var nowY = bridge.nowMinute / 60 * row
            var earliest = nowY
            var rows = bridge.blockRows
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

            Repeater {
                model: 24

                Rectangle {
                    y: index * root.row
                    width: parent.width
                    height: 1
                    color: root.line
                }
            }

            Repeater {
                id: hourLabels
                objectName: "hourLabels"
                model: bridge ? bridge.hours : 0

                Text {
                    objectName: "hourLabel"
                    x: 4
                    y: index * root.row + 2
                    width: 56
                    text: model.label
                    color: root.ink
                    font.family: "Roboto Flex"
                    font.pixelSize: 11
                    font.weight: 500
                }
            }

            Repeater {
                id: weekBlocks
                objectName: "weekBlocks"
                model: bridge ? bridge.blocks : 0

                EventBlock {
                    objectName: "weekBlock"
                    x: 64 + model.day * root.dayWidth + 3
                    y: model.start / 60 * root.row
                    width: Math.max(8, root.dayWidth - 8)
                    height: Math.max(36, (model.end - model.start) / 60 * root.row - 2)
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    category: model.category
                    title: model.title
                    detail: model.detail
                    past: model.past
                    accessName: model.title
                }
            }

            Rectangle {
                objectName: "nowLine"
                visible: !!bridge && bridge.nowDay >= 0
                x: 64
                y: (bridge ? bridge.nowMinute : 0) / 60 * root.row
                width: parent.width - 64
                height: 2
                color: root.now
                z: 3
            }
        }
    }

    Rectangle {
        id: drawer
        objectName: "homeworkDrawer"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: root.phone ? parent.width : 320
        height: root.phone ? column.implicitHeight + 16 : parent.height
        color: root.drawerFill

        Column {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 16
            spacing: 8

            Text {
                objectName: "homeworkCount"
                width: parent.width
                text: !bridge
                      ? ""
                      : (bridge.homeworkCount === 1
                         ? "1 still needs a time"
                         : bridge.homeworkCount + " still need a time")
                color: root.ink
                font.family: "Roboto Flex"
                font.pixelSize: 14
                font.weight: 600
                wrapMode: Text.WordWrap
            }

            Repeater {
                id: homeworkRows
                objectName: "homeworkRows"
                model: bridge ? bridge.homework : 0

                Text {
                    objectName: "homeworkTitle"
                    width: column.width
                    text: model.title
                    color: root.ink
                    font.family: "Roboto Flex"
                    font.pixelSize: 14
                    font.weight: 400
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
