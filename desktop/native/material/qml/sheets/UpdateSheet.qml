import QtQuick
import components 1.0

// A newer FlexWeek exists: centered floating pop-up hybrid of Option B (tinted version summary
// on left, What changed on right) and Option C (version icon card, green data-safety strip,
// clear buttons, downloading progress state).
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    desktopMaxWidth: 660
    objectName: "updateSheet"
    initialFocus: install
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    readonly property bool twoCol: !root.phone && bodyGrid.width >= 520

    Grid {
        id: bodyGrid
        width: parent.width
        columns: root.twoCol ? 2 : 1
        columnSpacing: 16
        rowSpacing: 14
        readonly property real leftW: root.twoCol ? Math.round((width - 16) * 0.44) : width
        readonly property real rightW: root.twoCol ? (width - 16 - leftW) : width

        // Left: Option B+C tinted version summary panel + green data-safety strip
        Rectangle {
            id: summaryCard
            width: bodyGrid.leftW
            implicitHeight: summaryCol.implicitHeight + 32
            height: root.twoCol ? Math.max(implicitHeight, rightCol.implicitHeight) : implicitHeight
            radius: pal.cornerFor(16)
            color: pal.primaryContainer
            border.width: root.highContrast ? 1.5 : 1
            border.color: root.highContrast ? pal.outline : Qt.rgba(pal.primary.r, pal.primary.g, pal.primary.b, 0.22)

            Column {
                id: summaryCol
                x: 16
                y: 16
                width: parent.width - 32
                spacing: 12

                Row {
                    spacing: 12
                    Rectangle {
                        width: 44
                        height: 44
                        radius: pal.cornerFor(12)
                        color: pal.primary
                        anchors.verticalCenter: parent.verticalCenter
                        M3Icon {
                            anchors.centerIn: parent
                            name: "download"
                            width: 22
                            height: 22
                            color: pal.inkPrimary
                        }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: "NEW RELEASE"
                            color: pal.primary
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(10)
                            font.weight: 700
                            font.letterSpacing: 0.9
                        }
                        Text {
                            text: root.f.version ? "Version " + root.f.version : "Update ready"
                            color: pal.inkPrimaryContainer
                            font.family: M3Font.heading
                            font.pixelSize: M3Font.px(18)
                            font.weight: 700
                        }
                        Text {
                            visible: !!(root.f.current && root.f.current !== "")
                            text: "Current: " + (root.f.current || "")
                            color: pal.inkPrimaryContainer
                            opacity: 0.8
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(12)
                        }
                    }
                }

                // Option C green safety strip holding the exact updateDetail message
                Rectangle {
                    width: parent.width
                    implicitHeight: safetyRow.implicitHeight + 20
                    height: implicitHeight
                    radius: pal.cornerFor(12)
                    color: pal.statusDoneTint
                    border.width: 1
                    border.color: Qt.rgba(pal.statusDone.r, pal.statusDone.g, pal.statusDone.b, 0.3)

                    Row {
                        id: safetyRow
                        x: 12
                        y: 10
                        width: parent.width - 24
                        spacing: 8
                        M3Icon {
                            name: "verified_user"
                            width: 18
                            height: 18
                            anchors.top: parent.top
                            anchors.topMargin: 2
                            color: pal.statusDone
                        }
                        Text {
                            objectName: "updateDetail"
                            width: parent.width - 26
                            text: root.f.detail ? root.f.detail : ""
                            color: pal.statusDone
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(13)
                            font.weight: 500
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }

        // Right: What changed release notes + downloading progress state
        Column {
            id: rightCol
            width: bodyGrid.rightW
            spacing: 12

            Rectangle {
                visible: !!(root.f.notes && root.f.notes !== "")
                width: parent.width
                implicitHeight: notesCol.implicitHeight + 28
                height: implicitHeight
                radius: pal.cornerFor(16)
                color: pal.panelSurface
                border.width: 1
                border.color: pal.outlineVariant

                Column {
                    id: notesCol
                    x: 16
                    y: 14
                    width: parent.width - 32
                    spacing: 8

                    Text {
                        text: "RELEASE NOTES"
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(10)
                        font.weight: 700
                        font.letterSpacing: 0.8
                    }
                    Text {
                        objectName: "updateNotes"
                        visible: text !== ""
                        width: parent.width
                        text: root.f.notes ? root.f.notes : ""
                        color: pal.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        lineHeight: 1.35
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // Status / download progress box
            Rectangle {
                visible: root.f.busy === true || !!(root.f.status && root.f.status !== "")
                width: parent.width
                implicitHeight: statusInner.implicitHeight + 24
                height: implicitHeight
                radius: pal.cornerFor(14)
                color: root.f.problem ? pal.errorContainer : pal.panelSurface
                border.width: 1
                border.color: root.f.problem ? pal.error : pal.outlineVariant

                Column {
                    id: statusInner
                    x: 14
                    y: 12
                    width: parent.width - 28
                    spacing: 10

                    Item {
                        width: parent.width
                        implicitHeight: Math.max(statusText.implicitHeight, pctText.implicitHeight)
                        height: implicitHeight
                        Text {
                            id: statusText
                            objectName: "updateStatus"
                            visible: text !== ""
                            width: pctText.visible ? parent.width - pctText.implicitWidth - 8 : parent.width
                            text: root.f.status ? root.f.status : ""
                            color: root.f.problem ? pal.error : pal.inkSurface
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(13)
                            font.weight: 500
                            wrapMode: Text.WordWrap
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                        Text {
                            id: pctText
                            visible: root.f.busy === true && track.value >= 0
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: Math.round(Math.max(0, Math.min(1, track.value)) * 100) + "%"
                            color: pal.primary
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(13)
                            font.weight: 700
                        }
                    }

                    Rectangle {
                        id: track
                        objectName: "updateProgress"
                        visible: root.f.busy === true
                        width: parent.width
                        height: 8
                        radius: 4
                        color: pal.wellSurface
                        clip: true
                        readonly property real value: root.f.progress !== undefined ? root.f.progress : -1
                        Accessible.role: Accessible.ProgressBar
                        Accessible.name: "Downloading the update"
                        Rectangle {
                            id: fill
                            height: parent.height
                            radius: 4
                            color: pal.primary
                            width: track.value >= 0 ? track.width * track.value : track.width * 0.3
                            x: 0
                            SequentialAnimation on x {
                                running: track.visible && track.value < 0 && !root.reduceMotion && Motion.pace > 0
                                loops: Animation.Infinite
                                NumberAnimation { from: 0; to: track.width * 0.7; duration: Motion.travel(900, false) }
                                NumberAnimation { from: track.width * 0.7; to: 0; duration: Motion.travel(900, false) }
                            }
                        }
                    }
                }
            }
        }
    }

    leading: Button {
        objectName: "updateSkip"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Skip this version"
        accessName: "Skip this version"
        onClicked: root.sheets.updateSkip()
    }
    trailing: Row {
        spacing: 8
        Button {
            objectName: "updateLater"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Not now"
            accessName: "Not now"
            onClicked: root.sheets.closeSheet()
        }
        Button {
            id: install
            objectName: "updateInstall"
            enabled: root.f.busy !== true
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            icon: "download"
            text: "Update now"
            accessName: "Update now"
            onClicked: root.sheets.updateInstall()
        }
    }
}
