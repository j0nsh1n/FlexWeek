import QtQuick
import components 1.0

// What shows over everything while an alarm rings: its name and time, then Snooze and Dismiss. Esc and Enter
// dismiss, as they do in the Widgets dialog. A tap outside the card does nothing: an alarm is meant to be
// answered. Focus goes back to where it was.
FocusScope {
    id: root
    objectName: "ringScreen"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    readonly property var ring: bridge ? bridge.ring : null
    readonly property bool open: ring ? ring.open : false
    readonly property var f: ring ? ring.form : ({})
    property Item before: null
    signal restoreFocus(Item item)

    anchors.fill: parent
    visible: open

    M3Palette { id: pal; theme: root.theme }

    onOpenChanged: {
        if (open) {
            before = Window.activeFocusItem
            Qt.callLater(function () { dismissButton.forceActiveFocus() })
        } else {
            var held = before
            before = null
            Qt.callLater(function () {
                if (held && held.visible)
                    held.forceActiveFocus()
                else
                    root.restoreFocus(null)
            })
        }
    }

    Rectangle {
        anchors.fill: parent
        objectName: "ringScrim"
        color: "#000000"
        // Darker in dark, where the card and the page are close greys: a ringing alarm must stand out.
        opacity: pal.dark ? 0.7 : 0.32
        // Takes every click so nothing under the ring is reached.
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }
    }
    Rectangle {
        id: card
        objectName: "ringCard"
        width: Math.min(400, Math.max(0, root.width - 32))
        height: content.implicitHeight + 48
        anchors.centerIn: parent
        radius: 28
        color: pal.surfaceContainerHigh
        border.width: root.highContrast ? 1.5 : (pal.dark ? 1 : 0)
        border.color: root.highContrast ? pal.outline : pal.outlineVariant
        Column {
            id: content
            x: 24
            y: 24
            width: card.width - 48
            spacing: 16
            Text {
                objectName: "ringTitle"
                width: parent.width
                text: root.f.title ? root.f.title : ""
                color: pal.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(24)
                wrapMode: Text.WordWrap
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
            Text {
                objectName: "ringDetail"
                width: parent.width
                text: root.f.detail ? root.f.detail : ""
                color: pal.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(16)
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
            Text {
                objectName: "ringPlaying"
                visible: !!root.f.playing
                width: parent.width
                text: root.f.playing ? root.f.playing : ""
                color: pal.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(14)
                wrapMode: Text.WordWrap
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
            Button {
                objectName: "ringSpotify"
                visible: !!root.f.spotify
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "tonal"
                text: "Open in Spotify"
                accessName: text
                onClicked: root.ring.openSpotify()
            }
            Item {
                width: parent.width
                height: 40
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    Button {
                        objectName: "ringSnooze"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: root.f.snoozeLabel ? root.f.snoozeLabel : "Snooze"
                        accessName: text
                        onClicked: root.ring.snooze()
                    }
                    Button {
                        id: dismissButton
                        objectName: "ringDismiss"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "filled"
                        text: "Dismiss"
                        accessName: text
                        onClicked: root.ring.dismiss()
                    }
                }
            }
        }
    }

    Accessible.role: Accessible.Dialog
    Accessible.name: root.f.title ? root.f.title : "Alarm"
    // BeforeItem: Tab stays on the ring, and Enter answers it wherever the focus is.
    Keys.priority: Keys.BeforeItem
    Keys.onTabPressed: (event) => {
        FocusCycle.take(FocusCycle.nextItem([card], 1, Window.activeFocusItem), 1)
        event.accepted = true
    }
    Keys.onBacktabPressed: (event) => {
        FocusCycle.take(FocusCycle.nextItem([card], -1, Window.activeFocusItem), -1)
        event.accepted = true
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: root.open
        onActivated: root.ring.dismiss()
    }
    Keys.onReturnPressed: (event) => { if (root.open) { root.ring.dismiss(); event.accepted = true } }
    Keys.onEnterPressed: (event) => { if (root.open) { root.ring.dismiss(); event.accepted = true } }
}
