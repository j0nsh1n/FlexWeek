import QtQuick
import components 1.0

// Dedicated phone pairing pop-up dialog (hybrid of Option A + Option C):
// computer <-> phone graphic header, large 4+4 one-time code tiles, live 5-min countdown bar,
// tries left, Copy code / Start a new code, 3 numbered steps, and n0 relay privacy note.
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
    property real fraction: 1.0
    property bool copied: false
    property string relayNote: ""
    signal copyRequested()
    signal restartRequested()
    signal dismissed()

    anchors.fill: parent
    visible: open
    enabled: open
    z: 30

    M3Palette { id: pal; theme: root.theme }

    readonly property string compactCode: root.code.replace(/[\s\-]+/g, "")
    readonly property string firstHalf: compactCode.length >= 8 ? compactCode.slice(0, 4) : root.code
    readonly property string secondHalf: compactCode.length >= 8 ? compactCode.slice(4, 8) : ""

    onOpenChanged: {
        if (open)
            Qt.callLater(function() { copyBtn.forceActiveFocus() })
    }

    Keys.onEscapePressed: (event) => {
        if (root.open) {
            root.dismissed()
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
        width: root.phone ? Math.max(0, root.width - 24) : Math.min(540, Math.max(320, root.width - 48))
        height: Math.min(root.height - 32, inner.implicitHeight + 48)
        anchors.centerIn: parent
        radius: pal.cornerFor(24)
        color: pal.dialogSurface
        border.width: root.highContrast ? 1.5 : (pal.dark ? 1 : 0)
        border.color: root.highContrast ? pal.outline : pal.outlineVariant
        clip: true
        TapHandler {}

        Flickable {
            anchors.fill: parent
            anchors.margins: 24
            contentWidth: width
            contentHeight: inner.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: inner
                width: parent.width
                spacing: 16

                // Option C computer <-> phone graphic header
                Rectangle {
                    width: parent.width
                    height: 84
                    radius: pal.cornerFor(16)
                    color: pal.primaryContainer

                    Row {
                        anchors.centerIn: parent
                        spacing: 18

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 40
                                height: 40
                                radius: pal.cornerFor(12)
                                color: pal.cardSurface
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "computer"
                                    width: 22
                                    height: 22
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
                            spacing: 6
                            Rectangle {
                                width: 20
                                height: 2
                                radius: 1
                                anchors.verticalCenter: parent.verticalCenter
                                color: pal.primary
                                opacity: 0.45
                            }
                            Rectangle {
                                width: 28
                                height: 28
                                radius: 14
                                color: pal.primary
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "link"
                                    width: 16
                                    height: 16
                                    color: pal.inkPrimary
                                }
                            }
                            Rectangle {
                                width: 20
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
                                width: 40
                                height: 40
                                radius: pal.cornerFor(12)
                                color: pal.cardSurface
                                M3Icon {
                                    anchors.centerIn: parent
                                    name: "smartphone"
                                    width: 22
                                    height: 22
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

                // Eyebrow + 4+4 digit tiles
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
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 12

                        Rectangle {
                            width: Math.max(132, firstDigits.implicitWidth + 32)
                            height: 60
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
                                font.pixelSize: M3Font.px(28)
                                font.weight: 700
                                font.letterSpacing: 3
                            }
                        }

                        Text {
                            visible: root.secondHalf !== ""
                            anchors.verticalCenter: parent.verticalCenter
                            text: "·"
                            color: pal.inkMuted
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(24)
                            font.weight: 700
                        }

                        Rectangle {
                            visible: root.secondHalf !== ""
                            width: Math.max(132, secondDigits.implicitWidth + 32)
                            height: 60
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
                                font.pixelSize: M3Font.px(28)
                                font.weight: 700
                                font.letterSpacing: 3
                            }
                        }
                    }

                    // 5-minute countdown bar
                    Rectangle {
                        id: progressTrack
                        objectName: "pairingProgress"
                        width: parent.width
                        height: 6
                        radius: 3
                        color: pal.wellSurface
                        clip: true
                        Rectangle {
                            height: parent.height
                            radius: 3
                            width: parent.width * Math.max(0, Math.min(1, root.fraction))
                            color: root.fraction < 0.2 ? pal.warning : pal.primary
                        }
                    }

                    Text {
                        objectName: "pairingStatus"
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: root.status || "Code works for 5:00. 3 tries left. It works once."
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(13)
                    }

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 10
                        Button {
                            id: copyBtn
                            objectName: "pairCopy"
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "filled"
                            icon: root.copied ? "check" : "content_copy"
                            text: root.copied ? "Copied" : "Copy code"
                            accessName: text
                            onClicked: root.copyRequested()
                        }
                        Button {
                            objectName: "pairNewCode"
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "tonal"
                            icon: "sync"
                            text: "Start a new code"
                            accessName: text
                            onClicked: root.restartRequested()
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
                    height: closeBtn.implicitHeight
                    Row {
                        anchors.left: parent.left
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
                    }
                }
            }
        }
    }
}
