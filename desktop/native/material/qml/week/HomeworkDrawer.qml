import QtQuick
import components 1.0

// Homework that has no time yet: count, Plan my homework, cards, and the empty state.
Rectangle {
    id: drawer
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    signal cardMoved(point scene)
    signal cardDropped(string blockId, point scene)
    signal cardDragStarted(string title)

    readonly property int count: bridge ? bridge.week.homeworkCount : 0

    M3Palette { id: m3; theme: drawer.theme }

    color: m3.surfaceContainerLow
    implicitHeight: header.implicitHeight + (count > 0 ? list.contentHeight : empty.implicitHeight) + 40

    Column {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 12

        Row {
            width: parent.width
            spacing: 8
            Text {
                objectName: "homeworkHeading"
                width: parent.width - badge.width - parent.spacing
                text: "No time yet · drag onto a day"
                color: m3.inkSurface
                wrapMode: Text.WordWrap
                font.family: M3Font.family
                font.pixelSize: 16
                font.weight: 500
            }
            Rectangle {
                id: badge
                objectName: "homeworkBadge"
                width: Math.max(24, countText.implicitWidth + 12)
                height: 24
                radius: 12
                color: m3.secondaryContainer
                Text {
                    id: countText
                    objectName: "homeworkCount"
                    anchors.centerIn: parent
                    text: String(drawer.count)
                    color: m3.inkSecondaryContainer
                    font.family: M3Font.family
                    font.pixelSize: 12
                    font.weight: 500
                }
                Accessible.role: Accessible.StaticText
                Accessible.name: drawer.count === 1 ? "1 homework needs a time" : drawer.count + " homework need a time"
            }
        }

        Button {
            objectName: "planHomework"
            theme: drawer.theme
            density: drawer.density
            reduceMotion: drawer.reduceMotion
            highContrast: drawer.highContrast
            kind: "filled"
            icon: "schedule"
            text: "Plan my homework"
            enabled: drawer.count > 0
            onClicked: drawer.bridge.week.plan()
        }
    }

    Flickable {
        id: scroller
        objectName: "homeworkScroller"
        visible: drawer.count > 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.margins: 16
        anchors.topMargin: 12
        contentHeight: list.contentHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        function reveal(itemY, itemHeight) {
            if (itemY < contentY)
                contentY = itemY
            else if (itemY + itemHeight > contentY + height)
                contentY = itemY + itemHeight - height
        }

        Column {
            id: list
            readonly property real contentHeight: implicitHeight
            width: scroller.width
            spacing: 8

            Repeater {
                id: homeworkRows
                objectName: "homeworkRows"
                model: drawer.bridge ? drawer.bridge.week.homework : 0

                HomeworkCard {
                    id: homeworkCard
                    objectName: "homeworkCard"
                    width: list.width
                    theme: drawer.theme
                    density: drawer.density
                    reduceMotion: drawer.reduceMotion
                    highContrast: drawer.highContrast
                    title: model.title
                    detail: model.detail
                    tag: model.tag
                    tagKind: model.tagKind
                    reason: model.reason
                    onDragStarted: drawer.cardDragStarted(model.title)
                    onDragMoved: (scene) => drawer.cardMoved(scene)
                    onDropped: (scene) => drawer.cardDropped(model.blockId, scene)
                    onActivated: drawer.bridge.week.planOne(model.assignmentId)
                    onActiveFocusChanged: if (activeFocus) scroller.reveal(y, height)
                }
            }
        }
    }

    Column {
        id: empty
        objectName: "homeworkEmpty"
        visible: drawer.count === 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.margins: 16
        anchors.topMargin: 32
        spacing: 8
        M3Icon {
            anchors.horizontalCenter: parent.horizontalCenter
            name: "task_alt"
            width: 36
            height: 36
            color: m3.primary
        }
        Text {
            objectName: "homeworkEmptyText"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "Everything has a time."
            color: m3.inkMuted
            font.family: M3Font.family
            font.pixelSize: 14
            font.weight: 400
        }
    }
}
