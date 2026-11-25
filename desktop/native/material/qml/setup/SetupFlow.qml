import QtQuick
import QtQuick.Layouts
import components 1.0
import "../sheets"

// First-run setup: Option B horizontal top stepper bar (frees full width for the 2x2 choice grid
// beside the live week preview) and a dedicated pinned bottom bar so no card is cut off above buttons.
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

    M3Palette { id: m3Palette; theme: root.theme }

    // The week and the picked list sit beside the cards on desktop, or under them when narrow.
    readonly property bool split: !phone && column.width >= 720
    readonly property real cardsWidth: split ? Math.floor((column.width - 24) * 0.58) : column.width

    function pageFor(step) {
        // Steps 0 to 2 were the style pages; setup starts at School hours, step 3.
        return [weekPage, homeworkPage, remindersPage][step - 3]
    }

    // Horizontal top stepper bar (Option B)
    Rectangle {
        id: rail
        objectName: "setupRail"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.phone ? 56 : 68
        color: m3Palette.panelSurface
        z: 2

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: m3Palette.outlineVariant
        }

        Item {
            width: Math.min(1080, parent.width - (root.phone ? 32 : 48))
            height: parent.height
            anchors.horizontalCenter: parent.horizontalCenter

            // Brand lockup on left
            Row {
                id: topBrand
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Rectangle {
                    width: 32
                    height: 32
                    radius: m3Palette.cornerFor(10)
                    color: m3Palette.primary
                    anchors.verticalCenter: parent.verticalCenter
                    M3Icon {
                        anchors.centerIn: parent
                        name: "school"
                        width: 18
                        height: 18
                        color: m3Palette.inkPrimary
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Set up FlexWeek"
                    color: m3Palette.inkSurface
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(17)
                    font.weight: 600
                }
            }

            // Mobile step text
            Text {
                visible: root.phone
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: "Step " + Math.max(1, Math.min(root.step - 2, 3)) + " of 3"
                color: m3Palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(13)
                font.weight: 600
            }

            // Desktop horizontal step pills
            Row {
                visible: !root.phone
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Repeater {
                    model: bridge ? bridge.railModel : null
                    Row {
                        id: stepWrap
                        required property var row
                        required property int index
                        spacing: 8

                        Rectangle {
                            visible: stepWrap.index > 0
                            width: 18
                            height: 2
                            radius: 1
                            anchors.verticalCenter: parent.verticalCenter
                            color: m3Palette.outlineVariant
                        }

                        Item {
                            id: railRow
                            objectName: "setupStep" + stepWrap.index
                            property bool keyDown: false
                            readonly property bool current: stepWrap.row.state === "current"
                            readonly property bool finished: stepWrap.row.state === "finished"
                            width: stepContent.implicitWidth + 24
                            height: 40
                            activeFocusOnTab: true

                            Rectangle {
                                anchors.fill: parent
                                radius: m3Palette.cornerFor(20)
                                color: railRow.current ? m3Palette.secondaryContainer : "transparent"
                                border.width: railRow.current && root.highContrast ? 1.5 : 0
                                border.color: m3Palette.outline
                            }
                            M3StateLayer {
                                anchors.fill: parent
                                radius: m3Palette.cornerFor(20)
                                color: m3Palette.inkSurface
                                hovered: railHover.hovered
                                down: railTap.pressed || railRow.keyDown
                                reduceMotion: root.reduceMotion
                            }
                            M3FocusRing {
                                anchors.fill: parent
                                anchors.margins: -4
                                ring: m3Palette.focusRing
                                ringRadius: m3Palette.cornerFor(20) + 4
                            }
                            Row {
                                id: stepContent
                                anchors.centerIn: parent
                                spacing: 8
                                Rectangle {
                                    id: badge
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 22
                                    height: 22
                                    radius: 11
                                    color: railRow.finished || railRow.current ? m3Palette.primary : "transparent"
                                    border.width: railRow.finished || railRow.current ? 0 : 1.5
                                    border.color: m3Palette.outline
                                    M3Icon {
                                        visible: railRow.finished
                                        anchors.centerIn: parent
                                        width: 14
                                        height: 14
                                        name: "check"
                                        color: m3Palette.inkPrimary
                                    }
                                    Text {
                                        visible: !railRow.finished
                                        anchors.centerIn: parent
                                        text: String(stepWrap.index + 1)
                                        color: railRow.current ? m3Palette.inkPrimary : m3Palette.inkMuted
                                        font.family: M3Font.family
                                        font.pixelSize: M3Font.px(11)
                                        font.weight: 700
                                    }
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: stepWrap.row.name
                                    color: railRow.current ? m3Palette.inkSecondaryContainer : m3Palette.inkSurface
                                    font.family: M3Font.family
                                    font.pixelSize: M3Font.px(13)
                                    font.weight: railRow.current ? 600 : 500
                                }
                            }
                            HoverHandler { id: railHover }
                            TapHandler { id: railTap; onTapped: root.bridge.setupJump(stepWrap.row.step) }
                            Accessible.role: Accessible.Button
                            Accessible.name: stepWrap.row.accessName
                            Accessible.onPressAction: root.bridge.setupJump(stepWrap.row.step)
                            Keys.onPressed: (event) => {
                                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    railRow.keyDown = true
                                    event.accepted = true
                                }
                            }
                            Keys.onReleased: (event) => {
                                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    if (railRow.keyDown)
                                        root.bridge.setupJump(stepWrap.row.step)
                                    railRow.keyDown = false
                                    event.accepted = true
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Main workspace between top stepper and pinned footer bar
    Item {
        id: stage
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: rail.bottom
        anchors.bottom: footerBar.top

        Item {
            id: column
            width: Math.min(1080, parent.width - (root.phone ? 32 : 48))
            height: parent.height
            x: (parent.width - width) / 2

            Column {
                id: head
                y: root.phone ? 14 : 20
                width: root.cardsWidth
                spacing: 4
                Text {
                    objectName: "setupTitle"
                    width: parent.width
                    text: bridge ? bridge.heading : ""
                    wrapMode: Text.WordWrap
                    color: m3Palette.inkSurface
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(root.phone ? 22 : 26)
                    font.weight: 600
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
                anchors.topMargin: 14
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                width: root.cardsWidth
                contentWidth: width
                contentHeight: pageHolder.height + 24
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Item {
                    id: pageHolder
                    width: scroller.width
                    height: stack.implicitHeight
                    Column {
                        id: stack
                        width: parent.width
                        spacing: 16
                        Loader {
                            id: pageLoader
                            width: parent.width
                            sourceComponent: root.pageFor(root.step)
                            onLoaded: scroller.contentY = 0
                        }
                        SetupPreview {
                            visible: !root.split
                            width: parent.width
                            gridHeight: 220
                            bridge: root.bridge
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                        }
                    }
                }
            }

            Flickable {
                visible: root.split
                x: root.cardsWidth + 24
                anchors.top: head.top
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                width: column.width - root.cardsWidth - 24
                contentWidth: width
                contentHeight: splitPreview.implicitHeight + 16
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                SetupPreview {
                    id: splitPreview
                    width: parent.width
                    bridge: root.bridge
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                }
            }
        }
    }

    // Pinned bottom footer bar: separates action buttons cleanly from scrolling cards.
    Rectangle {
        id: footerBar
        objectName: "setupFooterBar"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: footerCol.implicitHeight + (root.phone ? 24 : 28)
        color: m3Palette.panelSurface
        z: 2

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            color: m3Palette.outlineVariant
        }

        Column {
            id: footerCol
            width: Math.min(1080, parent.width - (root.phone ? 32 : 48))
            anchors.centerIn: parent
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

            Item {
                width: parent.width
                readonly property bool stackedFooter: root.phone || (leftBtns.implicitWidth + rightBtns.implicitWidth + 16 > width)
                implicitHeight: stackedFooter
                    ? (leftBtns.visible ? leftBtns.implicitHeight + 8 : 0) + rightBtns.implicitHeight
                    : Math.max(leftBtns.implicitHeight, rightBtns.implicitHeight)
                height: implicitHeight

                Row {
                    id: leftBtns
                    visible: (bridge ? bridge.backVisible : false) || (bridge ? bridge.skipVisible : false)
                    anchors.left: parent.left
                    anchors.top: parent.stackedFooter ? parent.top : undefined
                    anchors.verticalCenter: parent.stackedFooter ? undefined : parent.verticalCenter
                    spacing: 8
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
                }

                Row {
                    id: rightBtns
                    anchors.right: parent.right
                    anchors.bottom: parent.stackedFooter ? parent.bottom : undefined
                    anchors.verticalCenter: parent.stackedFooter ? undefined : parent.verticalCenter
                    spacing: 8
                    Button {
                        objectName: "setupSkip"
                        visible: bridge ? bridge.skipStepVisible : false
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.skipLabel : "Skip this step"
                        onClicked: root.bridge.setupSkip()
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

    Component { id: weekPage; WeekPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: homeworkPage; HomeworkPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: remindersPage; RemindersPage { bridge: root.bridge; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }

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

    // A Setup change that would reach a week with its own edit asks here, over the step.
    PromptDialog {
        anchors.fill: parent
        z: 40
        visible: bridge && bridge.ask && bridge.ask.id !== undefined
        enabled: visible
        sheets: root.bridge
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        phone: root.phone
        onVisibleChanged: if (visible) Qt.callLater(focusFirst)
    }
}
