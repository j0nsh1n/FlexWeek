import QtQuick
import components 1.0
import "../account"
import "../setup"

// School's days and times every week: one row inside a group, a draft until Save.
Item {
    id: root
    property var theme: Ui.theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    objectName: "row_schoolHours"

    implicitHeight: col.implicitHeight + 32
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

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
        Text {
            width: parent.width
            text: root.st.schoolNote || ""
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
        }
        Text {
            objectName: "schoolThisWeek"
            visible: (root.st.thisWeek || "") !== ""
            width: parent.width
            text: root.st.thisWeek || ""
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
        }
        DayChips {
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            width: parent.width
            prefix: "schoolDay"
            accessPrefix: "School on "
            names: root.st.dayNames || []
            days: root.st.schoolDays || []
            onToggled: (day) => root.panel.toggleSchoolDay(day)
        }
        Flow {
            width: parent.width
            spacing: 12
            AccountField {
                objectName: "schoolStart"
                width: 132
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                ground: palette.surfaceContainerLow
                label: "Starts"
                accessName: "School starts"
                text: root.st.schoolStart || ""
                onCommitted: (value) => root.panel.setSchoolStart(value)
            }
            AccountField {
                objectName: "schoolEnd"
                width: 132
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                ground: palette.surfaceContainerLow
                label: "Ends"
                accessName: "School ends"
                text: root.st.schoolEnd || ""
                onCommitted: (value) => root.panel.setSchoolEnd(value)
            }
        }
        Text {
            objectName: "schoolHint"
            visible: !(root.st.schoolDays || []).length
            width: parent.width
            text: root.st.noSchoolDays || ""
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
        }
        Text {
            objectName: "schoolError"
            visible: (root.st.schoolError || "") !== ""
            width: parent.width
            text: root.st.schoolError || ""
            color: palette.error
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            wrapMode: Text.WordWrap
        }
        Row {
            spacing: 8
            Button {
                objectName: "saveSchoolHours"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Save school hours"
                enabled: !!root.st.schoolDirty
                onClicked: root.panel.saveSchoolHours()
            }
            Button {
                objectName: "discardSchoolHours"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "text"
                text: "Undo changes"
                enabled: !!root.st.schoolDirty
                onClicked: root.panel.discardSchoolHours()
            }
        }
    }
}
