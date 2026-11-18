import QtQuick
import components 1.0
import "../account"
import "../setup"

// Study hours (when homework may go) and protected times (when it must stay away): one row inside a
// group, a draft until Save.
Item {
    id: root
    property var theme: Ui.theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    objectName: "row_studyHours"

    implicitHeight: col.implicitHeight + 32
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    component Sub: Text {
        M3Palette { id: pal; theme: Ui.theme }
        width: parent.width
        color: pal.primary
        font.family: M3Font.heading
        font.pixelSize: M3Font.px(14)
        font.weight: 500
    }
    component Help: Text {
        M3Palette { id: pal; theme: Ui.theme }
        width: parent.width
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Column {
        id: col
        x: 16
        y: 16
        width: root.width - 32
        spacing: 12
        Help { text: root.st.studyNote || "" }

        Sub { text: "When may FlexWeek plan homework?" }
        Help {
            objectName: "noStudyHours"
            visible: !(root.st.workWindows || []).length
            text: root.st.noStudyHours || ""
        }
        Flow {
            width: parent.width
            spacing: 8
            Repeater {
                model: root.st.workPresets || []
                Button {
                    required property var modelData
                    objectName: "workPreset" + modelData.name.replace(/ /g, "")
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "tonal"
                    text: modelData.name
                    onClicked: root.panel.addWorkPreset(modelData.name)
                }
            }
            Button {
                objectName: "addWork"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "text"
                text: "Add other hours"
                onClicked: root.panel.addWorkCustom()
            }
        }
        Repeater {
            model: root.st.workWindows || []
            delegate: Rectangle {
                id: win
                required property var modelData
                required property int index
                width: col.width
                implicitHeight: inner.implicitHeight + 32
                height: implicitHeight
                radius: 16
                color: palette.surfaceContainerLow
                border.width: root.highContrast ? 1.5 : 1
                border.color: palette.outlineVariant
                Column {
                    id: inner
                    x: 16
                    y: 16
                    width: parent.width - 32
                    spacing: 12
                    DayChips {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        width: parent.width
                        prefix: "workDay" + win.index + "-"
                        accessPrefix: "Study hours on "
                        names: root.st.dayNames || []
                        days: win.modelData.days
                        onToggled: (day) => root.panel.toggleWorkDay(win.index, day)
                    }
                    Flow {
                        width: parent.width
                        spacing: 12
                        AccountField {
                            objectName: "workStart" + win.index
                            width: 132
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "From"
                            accessName: "Study hours start"
                            text: win.modelData.start
                            onCommitted: (value) => root.panel.setWorkStart(win.index, value)
                        }
                        AccountField {
                            objectName: "workEnd" + win.index
                            width: 132
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "To"
                            accessName: "Study hours end"
                            text: win.modelData.end
                            onCommitted: (value) => root.panel.setWorkEnd(win.index, value)
                        }
                        AccountField {
                            objectName: "workSubject" + win.index
                            width: 200
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "Only for (optional)"
                            accessName: "Only for this subject"
                            text: win.modelData.subject
                            onCommitted: (value) => root.panel.setWorkSubject(win.index, value)
                        }
                        Button {
                            objectName: "workRemove" + win.index
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "text"
                            text: "Remove"
                            accessName: "Remove these study hours"
                            onClicked: root.panel.removeWorkWindow(win.index)
                        }
                    }
                }
            }
        }

        Sub { text: "When must homework stay away?" }
        Help {
            objectName: "noProtected"
            visible: !(root.st.protectedWindows || []).length
            text: root.st.noProtected || ""
        }
        Button {
            objectName: "addProtected"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Add protected time"
            onClicked: root.panel.addProtected()
        }
        Repeater {
            model: root.st.protectedWindows || []
            delegate: Rectangle {
                id: prot
                required property var modelData
                required property int index
                width: col.width
                implicitHeight: pinner.implicitHeight + 32
                height: implicitHeight
                radius: 16
                color: palette.surfaceContainerLow
                border.width: root.highContrast ? 1.5 : 1
                border.color: palette.outlineVariant
                Column {
                    id: pinner
                    x: 16
                    y: 16
                    width: parent.width - 32
                    spacing: 12
                    DayChips {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        width: parent.width
                        prefix: "protectedDay" + prot.index + "-"
                        accessPrefix: "Protected time on "
                        names: root.st.dayNames || []
                        days: prot.modelData.days
                        onToggled: (day) => root.panel.toggleProtectedDay(prot.index, day)
                    }
                    SegmentedButton {
                        objectName: "protectedKind" + prot.index
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        choices: root.st.protectedKinds || []
                        current: prot.modelData.kind
                        accessName: "Kind of time"
                        onSelected: (value) => root.panel.setProtectedKind(prot.index, value)
                    }
                    Flow {
                        width: parent.width
                        spacing: 12
                        AccountField {
                            objectName: "protectedStart" + prot.index
                            width: 132
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "From"
                            accessName: "Protected time start"
                            text: prot.modelData.start
                            onCommitted: (value) => root.panel.setProtectedStart(prot.index, value)
                        }
                        AccountField {
                            objectName: "protectedEnd" + prot.index
                            width: 132
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "To"
                            accessName: "Protected time end"
                            text: prot.modelData.end
                            onCommitted: (value) => root.panel.setProtectedEnd(prot.index, value)
                        }
                        AccountField {
                            objectName: "protectedTitle" + prot.index
                            width: 200
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            ground: palette.surfaceContainerLow
                            label: "Name (optional)"
                            accessName: "Name of this protected time"
                            placeholder: "e.g. Piano"
                            text: prot.modelData.title
                            onCommitted: (value) => root.panel.setProtectedTitle(prot.index, value)
                        }
                        Button {
                            objectName: "protectedRemove" + prot.index
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: "text"
                            text: "Remove"
                            accessName: "Remove this protected time"
                            onClicked: root.panel.removeProtected(prot.index)
                        }
                    }
                }
            }
        }
        Text {
            objectName: "studyError"
            visible: (root.st.studyError || "") !== ""
            width: parent.width
            text: root.st.studyError || ""
            color: palette.error
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
        }
        Row {
            spacing: 8
            Button {
                objectName: "saveStudyHours"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Save study hours"
                enabled: !!root.st.studyDirty
                onClicked: root.panel.saveStudyHours()
            }
            Button {
                objectName: "discardStudyHours"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "text"
                text: "Undo changes"
                enabled: !!root.st.studyDirty
                onClicked: root.panel.discardStudyHours()
            }
        }
    }
}
