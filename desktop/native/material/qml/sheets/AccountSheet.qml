import QtQuick
import components 1.0
import "../account"

// Manage account, from More or Settings > This computer: the password, the recovery codes, the files
// that move the account, a week or a day in and out, and deleting the account. What is typed into the
// two password fields stays in them; the bridge is handed it with the one button that needs it.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "accountSheet"
    initialFocus: currentPassword
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        objectName: "accountLocation"
        width: parent.width
        text: root.f.info ? root.f.info : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        width: parent.width
        text: "Password"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Text {
        width: parent.width
        text: root.f.passwordNote ? root.f.passwordNote : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    AccountField {
        id: currentPassword
        objectName: "currentPassword"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        ground: pal.surfaceContainerHigh
        label: "Current password"
        secret: true
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
        onEdited: (value) => text = value
    }
    AccountField {
        id: newPassword
        objectName: "newPassword"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        ground: pal.surfaceContainerHigh
        label: "New password"
        secret: true
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
        onEdited: (value) => text = value
    }
    Button {
        objectName: "changePassword"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "filled"
        text: "Replace password"
        accessName: "Replace password"
        onClicked: root.sheets.accountAct("password", currentPassword.text, newPassword.text)
    }
    Text {
        width: parent.width
        text: "Recovery codes"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Text {
        width: parent.width
        text: root.f.codesNote ? root.f.codesNote : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "recoveryCount"
        width: parent.width
        text: root.f.codesStatus ? root.f.codesStatus : ""
        color: root.f.codesProblem ? pal.error : pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Button {
        objectName: "replaceCodes"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "tonal"
        text: "Replace recovery codes"
        accessName: "Replace recovery codes"
        onClicked: root.sheets.accountAct("codes", currentPassword.text, "")
    }
    Text {
        width: parent.width
        text: "Your data"
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Text {
        width: parent.width
        text: root.f.dataNote ? root.f.dataNote : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Flow {
        width: parent.width
        spacing: 8
        Repeater {
            model: root.f.files ? root.f.files : []
            delegate: Button {
                objectName: modelData.name
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "tonal"
                text: modelData.label
                accessName: modelData.label
                onClicked: root.sheets.accountAct(modelData.id, currentPassword.text, "")
            }
        }
    }
    // Deleting is apart from the rest and asks before it does anything.
    Button {
        objectName: "deleteAccount"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Delete account"
        accessName: "Delete account"
        onClicked: root.sheets.accountAct("delete", currentPassword.text, "")
    }
    trailing: Button {
        objectName: "accountClose"
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
