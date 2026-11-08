import QtQuick
import QtQuick.Layouts
import components 1.0

// First-run setup: the steps down the side (a line of text on a phone), one page at a time, and
// Back, Skip this step, Skip setup and Next under it. Every answer goes to the account bridge.
FocusScope {
    id: root
    objectName: "setupFlow"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    readonly property int step: bridge ? bridge.setupStep : 0
    readonly property int railWidth: phone ? 0 : 248

    M3Palette { id: m3Palette; theme: root.theme }

    function pageFor(step) {
        return [stylePage, lookPage, coloursPage, weekPage, homeworkPage, remindersPage, firstPage, donePage][step]
    }

    // Side rail: one row per step.
    Rectangle {
        id: rail
        objectName: "setupRail"
        visible: !root.phone
        width: root.railWidth
        height: parent.height
        color: m3Palette.surfaceContainerLow

        Column {
            x: 16
            y: 32
            width: parent.width - 32
            spacing: 4
            Text {
                text: "Set up FlexWeek"
                color: m3Palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(22)
                font.weight: 500
                bottomPadding: 16
            }
            Repeater {
                model: bridge ? bridge.railModel : null
                Item {
                    id: railRow
                    required property var row
                    required property int index
                    objectName: "setupStep" + index
                    width: parent.width
                    height: 48
                    activeFocusOnTab: true
                    property bool keyDown: false
                    readonly property bool current: row.state === "current"
                    readonly property bool finished: row.state === "finished"
                    Rectangle {
                        anchors.fill: parent
                        radius: 24
                        color: railRow.current ? m3Palette.secondaryContainer : "transparent"
                    }
                    M3StateLayer {
                        anchors.fill: parent
                        radius: 24
                        color: m3Palette.inkSurface
                        hovered: railHover.hovered
                        down: railTap.pressed || railRow.keyDown
                        reduceMotion: root.reduceMotion
                    }
                    M3FocusRing {
                        anchors.fill: parent
                        anchors.margins: -4
                        ring: m3Palette.focusRing
                        ringRadius: 28
                    }
                    Rectangle {
                        id: badge
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: 24
                        height: 24
                        radius: 12
                        color: railRow.finished ? m3Palette.primary : "transparent"
                        border.width: railRow.finished ? 0 : 2
                        border.color: railRow.current ? m3Palette.primary : m3Palette.outline
                        M3Icon {
                            visible: railRow.finished
                            anchors.centerIn: parent
                            width: 16
                            height: 16
                            name: "check"
                            color: m3Palette.inkPrimary
                        }
                        Text {
                            visible: !railRow.finished
                            anchors.centerIn: parent
                            text: String(railRow.index + 1)
                            color: railRow.current ? m3Palette.primary : m3Palette.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(12)
                            font.weight: 500
                        }
                    }
                    Text {
                        anchors.left: badge.right
                        anchors.leftMargin: 12
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: railRow.row.name
                        elide: Text.ElideRight
                        color: railRow.current ? m3Palette.inkSecondaryContainer : m3Palette.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        font.weight: 500
                    }
                    HoverHandler { id: railHover }
                    TapHandler { id: railTap; onTapped: root.bridge.setupJump(railRow.row.step) }
                    Accessible.role: Accessible.Button
                    Accessible.name: railRow.row.accessName
                    Accessible.onPressAction: root.bridge.setupJump(railRow.row.step)
                    Keys.onPressed: (event) => {
                        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            railRow.keyDown = true
                            event.accepted = true
                        }
                    }
                    Keys.onReleased: (event) => {
                        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            if (railRow.keyDown)
                                root.bridge.setupJump(railRow.row.step)
                            railRow.keyDown = false
                            event.accepted = true
                        }
                    }
                }
            }
        }
    }

    // The page column.
    Item {
        id: stage
        anchors.left: rail.visible ? rail.right : parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        Item {
            id: column
            width: Math.min(880, parent.width - (root.phone ? 32 : 64))
            height: parent.height
            x: (parent.width - width) / 2

            Column {
                id: head
                y: root.phone ? 16 : 32
                width: parent.width
                spacing: 8
                Text {
                    visible: root.phone
                    text: "Step " + Math.min(root.step + 1, 6) + " of 6"
                    color: m3Palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(12)
                    font.weight: 500
                }
                Text {
                    objectName: "setupTitle"
                    width: parent.width
                    text: bridge ? bridge.heading : ""
                    wrapMode: Text.WordWrap
                    color: m3Palette.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(root.phone ? 24 : 28)
                    font.weight: 400
                    Accessible.role: Accessible.Heading
                    Accessible.name: text
                }
                Text {
                    objectName: "setupNote"
                    width: parent.width
                    text: bridge ? bridge.note : ""
                    wrapMode: Text.WordWrap
                    color: m3Palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                }
            }

            Flickable {
                id: scroller
                objectName: "setupScroll"
                anchors.top: head.bottom
                anchors.topMargin: 16
                anchors.bottom: footer.top
                anchors.bottomMargin: 8
                width: parent.width
                contentWidth: width
                contentHeight: pageHolder.height + 16
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Item {
                    id: pageHolder
                    width: scroller.width
                    height: pageLoader.item ? pageLoader.item.implicitHeight : 0
                    Loader {
                        id: pageLoader
                        width: parent.width
                        sourceComponent: root.pageFor(root.step)
                        onLoaded: scroller.contentY = 0
                    }
                }
            }

            Column {
                id: footer
                anchors.bottom: parent.bottom
                anchors.bottomMargin: root.phone ? 16 : 24
                width: parent.width
                spacing: 8

                Text {
                    objectName: "setupProblem"
                    width: parent.width
                    visible: text !== ""
                    text: bridge ? bridge.setupProblem : ""
                    wrapMode: Text.WordWrap
                    color: m3Palette.error
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }
                Flow {
                    width: parent.width
                    spacing: 8
                    layoutDirection: Qt.LeftToRight
                    Button {
                        objectName: "setupBack"
                        visible: bridge ? bridge.backVisible : false
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.backLabel : "Back"
                        onClicked: root.bridge.setupBack()
                    }
                    Button {
                        objectName: "setupSkip"
                        visible: bridge ? bridge.skipVisible : false
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.skipLabel : "Skip this step"
                        onClicked: root.bridge.setupSkip()
                    }
                    Button {
                        objectName: "setupSkipAll"
                        visible: bridge ? bridge.skipVisible : false
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.skipAllLabel : "Skip setup"
                        onClicked: root.bridge.setupSkipAll()
                    }
                    Button {
                        objectName: "setupNext"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "filled"
                        text: bridge ? bridge.nextLabel : "Next"
                        onClicked: root.bridge.setupNext()
                    }
                }
            }
        }
    }

    Component { id: stylePage; StylePage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: lookPage; LookPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: coloursPage; ColoursPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: weekPage; WeekPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: homeworkPage; HomeworkPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: remindersPage; RemindersPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: firstPage; FirstPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: donePage; DonePage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }

    // Skip-without-keeping asks first when the Your week page holds times the student typed.
    Connections {
        target: root.bridge
        function onChanged() { skipDialog.open = root.bridge.skipOpen }
    }
    Dialog {
        id: skipDialog
        objectName: "setupSkipDialog"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        title: "Skip this step?"
        body: bridge ? bridge.skipBody : ""
        confirmText: bridge ? bridge.skipConfirm : "Skip"
        dismissText: bridge ? bridge.skipDismiss : "Cancel"
        onConfirmed: root.bridge.answerSkip("skip")
        onDismissed: root.bridge.answerSkip(bridge && bridge.skipDismissKeeps ? "keep" : "cancel")
    }
}
