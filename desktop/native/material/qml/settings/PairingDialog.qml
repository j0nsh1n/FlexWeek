import QtQuick
import components 1.0

// Dedicated phone pairing pop-up dialog (hybrid of Option A + Option C):
// computer <-> phone graphic header, responsive 4+4 one-time code tiles, live 5-min countdown bar
// backed strictly by a waiting offer, Copy code / Start a new code, 3 steps, n0 relay note,
// trapped Tab/Backtab cycle, focus-driven scrolling, and focus restoration on close.
FocusScope {
    id: root
    objectName: "pairingDialog"
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    property bool open: false
    property string code: ""
    property string status: ""
    property real fraction: 0.0
    property bool copied: false
    property string relayNote: ""
    signal copyRequested()
    signal restartRequested()
    signal dismissed()
    signal closed()

    anchors.fill: parent
    visible: open
    enabled: open
    focus: open
    z: 30

    M3Palette { id: pal; theme: root.theme }

    readonly property string compactCode: root.code.replace(/[\s\-]+/g, "")
    readonly property string firstHalf: compactCode.length >= 8 ? compactCode.slice(0, 4) : root.code
    readonly property string secondHalf: compactCode.length >= 8 ? compactCode.slice(4, 8) : ""
    readonly property int focusMargin: 6

    function ensureVisible(item) {
        if (!item)
            return
        var pos = item.mapToItem(dialogFlick.contentItem, 0, 0)
        var top = pos.y - focusMargin
        var bottom = pos.y + item.height + focusMargin
        var limit = Math.max(0, dialogFlick.contentHeight - dialogFlick.height)
        if (top < dialogFlick.contentY)
            dialogFlick.contentY = Math.max(0, top)
        else if (bottom > dialogFlick.contentY + dialogFlick.height)
            dialogFlick.contentY = Math.min(limit, bottom - dialogFlick.height)
    }

    function cycle(step) {
        var next = FocusCycle.nextItem([card], step, Window.activeFocusItem)
        FocusCycle.take(next, step)
        root.ensureVisible(next)
    }

    onOpenChanged: {
        if (open) {
            dialogFlick.contentY = 0
            Qt.callLater(function() { if (root.open) copyBtn.forceActiveFocus() })
        } else {
            root.closed()
        }
    }

    Accessible.role: Accessible.Dialog
    Accessible.name: "Pair a phone"
    Keys.priority: Keys.BeforeItem
    Keys.onEscapePressed: (event) => {
        if (root.open) {
            root.dismissed()
            event.accepted = true
        }
    }
    Keys.onTabPressed: (event) => {
        if (root.open) {
            root.cycle(1)
            event.accepted = true
        }
    }
    Keys.onBacktabPressed: (event) => {
        if (root.open) {
            root.cycle(-1)
            event.accepted = true
        }
    }

    Rectangle {
        id: scrim
        objectName: "pairingScrim"
        anchors.fill: parent
        color: "#000000"
        opacity: pal.dark ? 0.6 : 0.32
        TapHandler {
            onTapped: (eventPoint) => {
                var p = scrim.mapToItem(card, eventPoint.position.x, eventPoint.position.y)
                if (p.x < 0 || p.x >= card.width || p.y < 0 || p.y >= card.height)
                    root.dismissed()
            }
        }
    }

    Rectangle {
        id: card
        objectName: "pairingCard"
        z: 1
        width: root.phone ? Math.max(240, root.width - 24) : Math.min(540, Math.max(320, root.width - 48))
        height: Math.min(root.height - 32, inner.implicitHeight + 48)
        anchors.centerIn: parent
        radius: pal.cornerFor(24)
        color: pal.dialogSurface
        border.width: root.highContrast ? 1.5 : (pal.dark ? 1 : 0)
        border.color: root.highContrast ? pal.outline : pal.outlineVariant
        clip: true
        TapHandler {}

        Flickable {
            id: dialogFlick
            objectName: "pairingScroll"
            anchors.fill: parent
            anchors.margins: 24
            contentWidth: width
            contentHeight: inner.implicitHeight + 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: inner
                width: dialogFlick.width
                spacing: 16
                readonly property bool compact: width < 320
                readonly property real tileWidth: root.secondHalf !== ""
                    ? Math.min(168, Math.max(88, Math.floor((width - 28) / 2)))
                    : Math.min(260, width)
                readonly property int digitPx: Math.min(
                    M3Font.px(compact ? 22 : 28),
                    Math.max(15, Math.floor(tileWidth * 0.22))
                )

                // Option C computer <-> phone graphic header
                Rectangle {
                    width: parent.width
                    height: 84
                    radius: pal.cornerFor(16)
                    color: pal.primaryContainer

                    Row {
                        anchors.centerIn: parent
                        spacing: inner.compact ? 10 : 18

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 38
                                height: 38
                                radius: pal.cornerFor(12)
                                color: pal.cardSurface
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "computer"
                                    width: 20
                                    height: 20
                                    color: pal.primary
                                }
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "This computer"
                                color: pal.inkPrimaryContainer
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(11)
                                font.weight: 600
                            }
                        }

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: inner.compact ? 4 : 6
                            Rectangle {
                                width: inner.compact ? 10 : 20
                                height: 2
                                radius: 1
                                anchors.verticalCenter: parent.verticalCenter
                                color: pal.primary
                                opacity: 0.45
                            }
                            Rectangle {
                                width: 26
                                height: 26
                                radius: 13
                                color: pal.primary
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "link"
                                    width: 15
                                    height: 15
                                    color: pal.inkPrimary
                                }
                            }
                            Rectangle {
                                width: inner.compact ? 10 : 20
                                height: 2
                                radius: 1
                                anchors.verticalCenter: parent.verticalCenter
                                color: pal.primary
                                opacity: 0.45
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 38
                                height: 38
                                radius: pal.cornerFor(12)
                                color: pal.cardSurface
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "smartphone"
                                    width: 20
                                    height: 20
                                    color: pal.primary
                                }
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "Your phone"
                                color: pal.inkPrimaryContainer
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(11)
                                font.weight: 600
                            }
                        }
                    }
                }

                // Eyebrow + responsive 4+4 digit tiles
                Column {
                    width: parent.width
                    spacing: 10

                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: "ONE-TIME PAIRING CODE"
                        color: pal.primary
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(11)
                        font.weight: 700
                        font.letterSpacing: 1.0
                    }

                    // Accessible full code text for screen readers and tests
                    Text {
                        objectName: "pairingCodeText"
                        width: 1
                        height: 1
                        opacity: 0
                        text: root.code
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Pairing code " + root.code
                    }

                    Row {
                        id: tilesRow
                        objectName: "pairingTilesRow"
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: inner.compact ? 6 : 10

                        Rectangle {
                            objectName: "pairingTileFirst"
                            width: inner.tileWidth
                            height: Math.max(54, inner.digitPx + 30)
                            radius: pal.cornerFor(14)
                            color: pal.wellSurface
                            border.width: root.highContrast ? 1.5 : 1
                            border.color: root.highContrast ? pal.outline : pal.outlineVariant
                            Text {
                                id: firstDigits
                                anchors.centerIn: parent
                                text: root.firstHalf
                                color: pal.inkSurface
                                font.family: "JetBrains Mono, monospace"
                                font.pixelSize: inner.digitPx
                                font.weight: 700
                                font.letterSpacing: inner.compact ? 1.5 : 3
                            }
                        }

                        Text {
                            visible: root.secondHalf !== ""
                            anchors.verticalCenter: parent.verticalCenter
                            text: "·"
                            color: pal.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(22)
                            font.weight: 700
                        }

                        Rectangle {
                            objectName: "pairingTileSecond"
                            visible: root.secondHalf !== ""
                            width: inner.tileWidth
                            height: Math.max(54, inner.digitPx + 30)
                            radius: pal.cornerFor(14)
                            color: pal.wellSurface
                            border.width: root.highContrast ? 1.5 : 1
                            border.color: root.highContrast ? pal.outline : pal.outlineVariant
                            Text {
                                id: secondDigits
                                anchors.centerIn: parent
                                text: root.secondHalf
                                color: pal.inkSurface
                                font.family: "JetBrains Mono, monospace"
                                font.pixelSize: inner.digitPx
                                font.weight: 700
                                font.letterSpacing: inner.compact ? 1.5 : 3
                            }
                        }
                    }

                    // 5-minute countdown bar (only shown when backed by an active waiting offer)
                    Rectangle {
                        id: progressTrack
                        objectName: "pairingProgress"
                        visible: root.status !== ""
                        width: parent.width
                        height: 6
                        radius: 3
                        color: pal.wellSurface
                        clip: true
                        Rectangle {
                            height: parent.height
                            radius: 3
                            width: parent.width * Math.max(0, Math.min(1, root.fraction))
                            color: root.fraction < 0.2 ? pal.statusDueSoon : pal.primary
                        }
                    }

                    Text {
                        objectName: "pairingStatus"
                        visible: root.status !== ""
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: root.status
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(13)
                    }

                    Grid {
                        id: actionsGrid
                        objectName: "pairingActions"
                        readonly property real naturalWidth: copyBtn.implicitWidth + newCodeBtn.implicitWidth + 10
                        readonly property bool stacked: naturalWidth > inner.width
                        columns: stacked ? 1 : 2
                        columnSpacing: 10
                        rowSpacing: 8
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: stacked ? inner.width : naturalWidth

                        Button {
                            id: copyBtn
                            objectName: "pairCopy"
                            width: actionsGrid.stacked ? actionsGrid.width : implicitWidth
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "filled"
                            icon: root.copied ? "check" : "content_copy"
                            text: root.copied ? "Copied" : "Copy code"
                            accessName: text
                            onClicked: root.copyRequested()
                            onActiveFocusChanged: if (activeFocus) root.ensureVisible(this)
                        }
                        Button {
                            id: newCodeBtn
                            objectName: "pairNewCode"
                            width: actionsGrid.stacked ? actionsGrid.width : implicitWidth
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "tonal"
                            icon: "sync"
                            text: "Start a new code"
                            accessName: text
                            onClicked: root.restartRequested()
                            onActiveFocusChanged: if (activeFocus) root.ensureVisible(this)
                        }
                    }
                }

                // 3 numbered steps
                Column {
                    width: parent.width
                    spacing: 8
                    Repeater {
                        model: [
                            "Open FlexWeek on your phone.",
                            "Go to Settings and pick Link a computer.",
                            "Type this 8-character code — it works once."
                        ]
                        Row {
                            required property int index
                            required property string modelData
                            width: inner.width
                            spacing: 10
                            Rectangle {
                                width: 22
                                height: 22
                                radius: 11
                                color: pal.secondaryContainer
                                Text {
                                    anchors.centerIn: parent
                                    text: String(index + 1)
                                    color: pal.inkSecondaryContainer
                                    font.family: M3Font.family
                                    font.pixelSize: M3Font.px(11)
                                    font.weight: 700
                                }
                            }
                            Text {
                                width: parent.width - 32
                                anchors.verticalCenter: parent.verticalCenter
                                wrapMode: Text.WordWrap
                                text: modelData
                                color: pal.inkSurface
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(13)
                            }
                        }
                    }
                }

                // n0 relay privacy note
                Rectangle {
                    visible: root.relayNote !== ""
                    width: parent.width
                    implicitHeight: relayRow.implicitHeight + 20
                    height: implicitHeight
                    radius: pal.cornerFor(12)
                    color: pal.panelSurface
                    border.width: 1
                    border.color: pal.outlineVariant
                    Row {
                        id: relayRow
                        x: 12
                        y: 10
                        width: parent.width - 24
                        spacing: 10
                        M3Icon {
                            name: "wifi"
                            width: 18
                            height: 18
                            anchors.top: parent.top
                            anchors.topMargin: 2
                            color: pal.inkMuted
                        }
                        Text {
                            width: parent.width - 28
                            wrapMode: Text.WordWrap
                            text: root.relayNote
                            color: pal.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(12)
                        }
                    }
                }

                // Footer
                Item {
                    width: parent.width
                    implicitHeight: Math.max(waitRow.implicitHeight, closeBtn.implicitHeight)
                    height: implicitHeight
                    Row {
                        id: waitRow
                        anchors.left: parent.left
                        anchors.right: closeBtn.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: pal.primary
                        }
                        Text {
                            width: Math.max(0, parent.width - 16)
                            wrapMode: Text.WordWrap
                            text: "Waiting for your phone…"
                            color: pal.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(13)
                        }
                    }
                    Button {
                        id: closeBtn
                        objectName: "pairClose"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: "Close"
                        accessName: "Close pairing dialog"
                        onClicked: root.dismissed()
                        onActiveFocusChanged: if (activeFocus) root.ensureVisible(this)
                    }
                }
            }
        }
    }
}
