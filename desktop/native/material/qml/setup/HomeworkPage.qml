import QtQuick
import QtQuick.Layouts
import components 1.0
import "../account"

// How homework gets a time: planning style, drag step, and the hours it may be planned in.
Column {
    id: page
    objectName: "setupHomeworkPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 12

    M3Palette { id: palette; theme: page.theme }

    Repeater {
        model: bridge ? bridge.planningChoices : []
        ChoiceCard {
            required property var modelData
            width: page.width
            objectName: "setupPlanning-" + modelData.value
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            title: modelData.label
            note: modelData.note
            selected: page.bridge.planning === modelData.value
            onChosen: page.bridge.setPlanning(modelData.value)
        }
    }

    SectionTitle { theme: page.theme; text: bridge ? bridge.dragQuestion : "" }
    ChipRow {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupDragStep"
        accessPrefix: "Drag step "
        choices: bridge ? bridge.dragChoices : []
        current: bridge ? bridge.dragStep : 5
        onPicked: (value) => page.bridge.setDragStep(value)
    }

    SectionTitle { theme: page.theme; text: "When may FlexWeek plan homework?" }
    HelpText {
        objectName: "setupWorkMessage"
        theme: page.theme
        width: parent.width
        text: bridge ? bridge.workMessage : ""
    }
    HelpText { theme: page.theme; width: parent.width; text: bridge ? bridge.workPresetsNote : "" }
    Flow {
        width: parent.width
        spacing: 8
        Repeater {
            model: bridge ? bridge.workPresets : []
            Button {
                required property var modelData
                objectName: modelData.objectName
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                kind: "tonal"
                text: modelData.name
                enabled: page.bridge.canAddWindow
                onClicked: page.bridge.addWorkPreset(modelData.name)
            }
        }
        Button {
            objectName: "workWindowCustom"
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            kind: "outlined"
            text: "Add other hours"
            enabled: bridge ? bridge.canAddWindow : false
            onClicked: page.bridge.addWorkCustom()
        }
    }
    HelpText {
        objectName: "setupWorkLimit"
        theme: page.theme
        width: parent.width
        visible: text !== ""
        text: bridge ? bridge.workLimit : ""
    }
    Repeater {
        model: bridge ? bridge.workModel : null
        Rectangle {
            id: win
            required property var row
            required property int index
            width: page.width
            implicitHeight: inner.implicitHeight + 32
            height: implicitHeight
            radius: 16
            color: palette.surfaceContainerLow
            border.width: page.highContrast ? 1.5 : 1
            border.color: palette.outlineVariant
            Column {
                id: inner
                x: 16
                y: 16
                width: parent.width - 32
                spacing: 12
                DayChips {
                    width: parent.width
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    prefix: "setupWorkDay" + win.index + "-"
                    accessPrefix: "Homework hours on "
                    names: page.bridge.dayNames
                    days: win.row.days
                    onToggled: (day) => page.bridge.toggleWorkDay(win.index, day)
                }
                Flow {
                    width: parent.width
                    spacing: 12
                    AccountField {
                        objectName: "setupWorkStart" + win.index
                        width: 132
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "From"
                        accessName: "Homework hours start"
                        text: win.row.start
                        onCommitted: (value) => page.bridge.setWorkStart(win.index, value)
                    }
                    AccountField {
                        objectName: "setupWorkEnd" + win.index
                        width: 132
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "To"
                        accessName: "Homework hours end"
                        text: win.row.end
                        onCommitted: (value) => page.bridge.setWorkEnd(win.index, value)
                    }
                    AccountField {
                        objectName: "setupWorkSubject" + win.index
                        width: 200
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "Only for (optional)"
                        accessName: "Only for this subject"
                        text: win.row.subject
                        onCommitted: (value) => page.bridge.setWorkSubject(win.index, value)
                    }
                    Button {
                        objectName: "setupWorkRemove" + win.index
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        kind: "outlined"
                        text: "Remove"
                        accessName: "Remove these hours"
                        onClicked: page.bridge.removeWorkWindow(win.index)
                    }
                }
            }
        }
    }
}
