import QtQuick
import components 1.0

// About FlexWeek from More: the version, what FlexWeek is, and where the week is saved.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "aboutSheet"
    initialFocus: closeButton
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Row {
        width: parent.width
        spacing: 14
        // The logo brings its own rounded lime square with see-through corners, so nothing is drawn behind it.
        Image {
            objectName: "aboutLogo"
            width: 56
            height: 56
            sourceSize.width: 112
            sourceSize.height: 112
            fillMode: Image.PreserveAspectFit
            smooth: true
            source: root.f.logo ? root.f.logo : ""
            Accessible.ignored: true
        }
        Text {
            objectName: "aboutVersion"
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 70
            text: root.f.version ? root.f.version : ""
            color: pal.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(20)
            font.weight: 500
            wrapMode: Text.WordWrap
        }
    }
    Text {
        objectName: "aboutWhat"
        width: parent.width
        text: root.f.what ? root.f.what : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    TextEdit {
        objectName: "aboutWhere"
        width: parent.width
        readOnly: true
        selectByMouse: true
        text: root.f.where ? root.f.where : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: TextEdit.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Button {
        objectName: "aboutOpenFolder"
        visible: root.f.folder === true
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "tonal"
        text: "Open folder"
        accessName: "Open folder"
        onClicked: root.sheets.openAboutFolder()
    }
    trailing: Button {
        id: closeButton
        objectName: "aboutClose"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Close"
        accessName: "Close"
        onClicked: root.sheets.closeSheet()
    }
}
