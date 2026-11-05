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
    property bool passive: false
    signal cardMoved(point scene)
    signal cardDropped(string blockId, point scene)
    signal cardDragStarted(string title)

    readonly property int count: bridge ? bridge.week.homeworkCount : 0
    property alias planButton: planButton

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
            id: planButton
            objectName: "planHomework"
            theme: drawer.theme
            density: drawer.density
            reduceMotion: drawer.reduceMotion
            highContrast: drawer.highContrast
            kind: enabled ? "filled" : "text"
            mutedWhenDisabled: true
            icon: "schedule"
            text: "Plan my homework"
            enabled: drawer.count > 0
            activeFocusOnTab: enabled && !drawer.passive
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
                    passive: drawer.passive
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
                    onOpened: if (drawer.bridge && drawer.bridge.sheets) drawer.bridge.sheets.editHomework(model.assignmentId)
                    onMenuAsked: (mx, my) => drawer.openCardMenu(homeworkCard, model, mx, my)
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

    property Item menuOriginItem: null
    property var menuTargetModel: null

    function openCardMenu(item, cardModel, mx, my) {
        menuOriginItem = item
        menuTargetModel = {
            blockId: cardModel.blockId,
            assignmentId: cardModel.assignmentId
        }
        var mapped = item.mapToItem(drawer, mx, my)
        var menuX = Math.max(8, Math.min(mapped.x, drawer.width - cardMenu.width - 8))
        var menuY = Math.max(8, Math.min(mapped.y, drawer.height - cardMenu.height - 8))
        cardMenu.x = menuX
        cardMenu.y = menuY
        cardMenu.entries = [
            { label: "Edit", icon: "edit_note" },
            { label: "Place now", icon: "schedule" },
            { label: "Mark finished", icon: "check" },
            { label: "Delete", icon: "close" }
        ]
        cardMenu.cursor = 0
        cardMenu.open = true
        cardMenu.forceActiveFocus()
    }

    function closeCardMenu() {
        if (!cardMenu.open && !menuOriginItem && !menuTargetModel)
            return
        cardMenu.open = false
        var origin = menuOriginItem
        menuOriginItem = null
        menuTargetModel = null
        if (origin && origin.visible)
            origin.forceActiveFocus()
    }

    FocusScope {
        id: cardMenuOverlay
        anchors.fill: parent
        z: 50
        visible: cardMenu.open
        enabled: cardMenu.open

        Rectangle {
            id: cardMenuDim
            anchors.fill: parent
            color: "transparent"
            TapHandler {
                enabled: cardMenu.open
                onTapped: drawer.closeCardMenu()
            }
        }

        Menu {
            id: cardMenu
            objectName: "cardMenu"
            open: false
            focus: true
            activeFocusOnTab: open && !drawer.passive
            onActiveFocusChanged: {
                if (!activeFocus && open)
                    drawer.closeCardMenu()
            }
            theme: drawer.theme
            density: drawer.density
            reduceMotion: drawer.reduceMotion
            highContrast: drawer.highContrast
            onChosen: (index, label) => {
                var target = drawer.menuTargetModel
                drawer.closeCardMenu()
                if (!drawer.bridge || !target)
                    return
                if (label === "Edit") {
                    if (drawer.bridge.sheets)
                        drawer.bridge.sheets.editHomework(target.assignmentId)
                } else if (label === "Place now") {
                    drawer.bridge.week.planOne(target.assignmentId)
                } else if (label === "Mark finished") {
                    drawer.bridge.week.toggleDone(target.assignmentId)
                } else if (label === "Delete") {
                    if (drawer.bridge.sheets) {
                        if (drawer.bridge.sheets.askDeleteHomework)
                            drawer.bridge.sheets.askDeleteHomework(target.assignmentId)
                        else
                            drawer.bridge.sheets.askDeleteUnfinished(target.assignmentId)
                    }
                }
            }
            onDismissed: drawer.closeCardMenu()
        }
    }
}
