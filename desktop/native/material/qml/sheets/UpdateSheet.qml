import QtQuick
import components 1.0

// A newer FlexWeek exists. It says what, and does nothing until the student chooses.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "updateSheet"
    initialFocus: install
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        objectName: "updateDetail"
        width: parent.width
        text: root.f.detail ? root.f.detail : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "updateNotes"
        visible: text !== ""
        width: parent.width
        text: root.f.notes ? root.f.notes : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "updateStatus"
        visible: text !== ""
        width: parent.width
        text: root.f.status ? root.f.status : ""
        color: root.f.problem ? pal.error : pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Rectangle {
        id: track
        objectName: "updateProgress"
        visible: root.f.busy === true
        width: parent.width
        height: 4
        radius: 2
        color: pal.surfaceContainerHighest
        clip: true
        readonly property real value: root.f.progress !== undefined ? root.f.progress : -1
        Accessible.role: Accessible.ProgressBar
        Accessible.name: "Downloading the update"
        Rectangle {
            id: fill
            height: parent.height
            radius: 2
            color: pal.primary
            width: track.value >= 0 ? track.width * track.value : track.width * 0.3
            x: 0
            SequentialAnimation on x {
                running: track.visible && track.value < 0 && !root.reduceMotion
                loops: Animation.Infinite
                NumberAnimation { from: 0; to: track.width * 0.7; duration: 900 }
                NumberAnimation { from: track.width * 0.7; to: 0; duration: 900 }
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
            kind: "text"
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
            text: "Update now"
            accessName: "Update now"
            onClicked: root.sheets.updateInstall()
        }
    }
}
