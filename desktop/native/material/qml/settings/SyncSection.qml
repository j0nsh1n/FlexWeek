import QtQuick
import components 1.0

// Phone & sync: its own Settings section (Option A) with a single colored status word,
// dedicated warning lines, linked phones with red-outlined Remove buttons, and what syncs.
SectionPage {
    id: page
    objectName: "syncSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    M3Palette { id: m3; theme: Ui.theme }

    readonly property color statusColor: {
        var tone = page.st.syncStatusTone || "muted"
        if (tone === "ok")
            return m3.statusDone
        if (tone === "info")
            return m3.primary
        if (tone === "error")
            return m3.error
        if (tone === "warn")
            return m3.statusDueSoon
        return m3.inkMuted
    }

    // Status hero card (no synthetic state switcher; reflects live sync state only).
    Rectangle {
        id: statusCard
        objectName: "syncStatusCard"
        width: parent.width
        implicitHeight: statusCol.implicitHeight + 32
        height: implicitHeight
        radius: m3.cornerFor(16)
        color: m3.cardSurface
        border.width: Ui.highContrast ? 1.5 : 1
        border.color: Ui.highContrast ? m3.outline : m3.outlineVariant

        Column {
            id: statusCol
            x: 18
            y: 16
            width: parent.width - 36
            spacing: 12

            Item {
                width: parent.width
                implicitHeight: Math.max(iconTile.height, titleCol.implicitHeight, rightCol.implicitHeight)
                height: implicitHeight

                Rectangle {
                    id: iconTile
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 44
                    height: 44
                    radius: m3.cornerFor(12)
                    color: m3.primaryContainer
                    M3Icon {
                        anchors.centerIn: parent
                        name: "sync"
                        width: 22
                        height: 22
                        color: m3.inkPrimaryContainer
                    }
                }

                Column {
                    id: titleCol
                    anchors.left: iconTile.right
                    anchors.leftMargin: 14
                    anchors.right: rightCol.left
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2

                    Text {
                        width: parent.width
                        text: "Phone & sync"
                        color: m3.inkSurface
                        font.family: M3Font.heading
                        font.pixelSize: M3Font.px(18)
                        font.weight: 600
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        objectName: "syncWordsText"
                        width: parent.width
                        text: page.st.syncWords || "Link a phone to keep your week and homework in step."
                        color: m3.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(13)
                        wrapMode: Text.WordWrap
                    }
                }

                Row {
                    id: rightCol
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12

                    Text {
                        id: statusWord
                        objectName: "syncStatusWord"
                        anchors.verticalCenter: parent.verticalCenter
                        text: page.st.syncStatusWord || "Not linked"
                        color: page.statusColor
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        font.weight: 700
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Sync status: " + text
                    }

                    Item {
                        id: syncNowWrap
                        objectName: "row_syncNow"
                        visible: !!page.st.canSync
                        width: visible ? syncNowBtn.implicitWidth : 0
                        height: syncNowBtn.implicitHeight
                        anchors.verticalCenter: parent.verticalCenter
                        Button {
                            id: syncNowBtn
                            objectName: "syncNow"
                            theme: Ui.theme
                            density: Ui.density
                            reduceMotion: Ui.reduceMotion
                            highContrast: Ui.highContrast
                            kind: "filled"
                            icon: "sync"
                            text: page.st.syncBusy ? "Syncing..." : "Sync now"
                            enabled: !page.st.syncBusy
                            accessName: text
                            onClicked: page.panel.syncNow()
                        }
                    }
                }
            }

            // Dedicated clock warning line (always on its own line when present).
            Rectangle {
                visible: !!page.st.clockWarning
                width: parent.width
                implicitHeight: clockNote.implicitHeight + 4
                height: implicitHeight
                radius: m3.cornerFor(10)
                color: m3.statusDueSoonTint
                border.width: 1
                border.color: m3.statusDueSoon
                NoteRow {
                    id: clockNote
                    width: parent.width
                    key: "clockWarning"
                    visible: !!page.st.clockWarning
                    problem: true
                    text: page.st.clockWarning || ""
                }
            }

            // Dedicated sync problem line.
            Rectangle {
                visible: !!page.st.syncProblem
                width: parent.width
                implicitHeight: problemNote.implicitHeight + 4
                height: implicitHeight
                radius: m3.cornerFor(10)
                color: m3.errorContainer
                NoteRow {
                    id: problemNote
                    width: parent.width
                    key: "syncProblem"
                    visible: !!page.st.syncProblem
                    problem: true
                    text: page.st.syncProblem || ""
                }
            }
        }
    }

    // Linked phones & pairing group
    Group {
        GroupHeader { title: "Linked phones"; icon: "smartphone" }
        LinkRow {
            key: "pair"
            title: "Pair a phone"
            subtitle: page.st.pairCode
                ? "Enter this code on the phone: " + page.st.pairCode + (page.st.pairStatus ? ". " + page.st.pairStatus : "")
                : "Show a code to link a phone."
            trailing: ""
            onClicked: page.panel.pair()
        }
        Repeater {
            model: page.st.phoneRows || []
            delegate: ActionRow {
                required property var modelData
                key: "phone_" + modelData.id
                title: modelData.name
                subtitle: modelData.seen
                buttonText: "Remove"
                buttonKind: "danger-outlined"
                onActivated: page.panel.askRemovePhone(modelData.id)
            }
        }
        SettingsRow {
            visible: !!page.st.pairError
            title: "Pairing"
            subtitle: page.st.pairError || ""
            objectName: "row_pairError"
        }
        NoteRow {
            key: "relayNote"
            text: page.st.relayNote || ""
        }
    }

    // Side-by-side summary of what syncs vs what stays local on each device.
    Grid {
        id: infoGrid
        width: parent.width
        columns: width >= 520 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12
        readonly property real cellWidth: columns === 2 ? (width - 12) / 2 : width

        Rectangle {
            width: infoGrid.cellWidth
            implicitHeight: Math.max(syncsCol.implicitHeight, localCol.implicitHeight) + 28
            height: implicitHeight
            radius: m3.cornerFor(16)
            color: m3.cardSurface
            border.width: Ui.highContrast ? 1.5 : 1
            border.color: Ui.highContrast ? m3.outline : m3.outlineVariant
            Column {
                id: syncsCol
                x: 16
                y: 14
                width: parent.width - 32
                spacing: 6
                Row {
                    spacing: 8
                    M3Icon {
                        name: "sync"
                        width: 16
                        height: 16
                        anchors.verticalCenter: parent.verticalCenter
                        color: m3.primary
                    }
                    Text {
                        text: "Syncs between devices"
                        color: m3.inkSurface
                        font.family: M3Font.heading
                        font.pixelSize: M3Font.px(14)
                        font.weight: 600
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Your week, homework, study hours, school hours, reminders and planning preferences."
                    color: m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(13)
                }
            }
        }

        Rectangle {
            width: infoGrid.cellWidth
            implicitHeight: Math.max(syncsCol.implicitHeight, localCol.implicitHeight) + 28
            height: implicitHeight
            radius: m3.cornerFor(16)
            color: m3.cardSurface
            border.width: Ui.highContrast ? 1.5 : 1
            border.color: Ui.highContrast ? m3.outline : m3.outlineVariant
            Column {
                id: localCol
                x: 16
                y: 14
                width: parent.width - 32
                spacing: 6
                Row {
                    spacing: 8
                    M3Icon {
                        name: "computer"
                        width: 16
                        height: 16
                        anchors.verticalCenter: parent.verticalCenter
                        color: m3.inkMuted
                    }
                    Text {
                        text: "Stays on each device"
                        color: m3.inkSurface
                        font.family: M3Font.heading
                        font.pixelSize: M3Font.px(14)
                        font.weight: 600
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Look preset, light or dark mode, text size, keyboard shortcuts and panel widths."
                    color: m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(13)
                }
            }
        }
    }
}
