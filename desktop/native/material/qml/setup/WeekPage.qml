import QtQuick
import QtQuick.Layouts
import components 1.0
import "../account"

// Clock, week start, school, sports and jobs, and the evening cutoff.
Column {
    id: page
    objectName: "setupWeekPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 12

    M3Palette { id: palette; theme: page.theme }

    SectionTitle { theme: page.theme; text: "Clock" }
    ChipRow {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupClock"
        accessPrefix: "Clock: "
        choices: [{value: "12", label: "12-hour clock (4:00 PM)"}, {value: "24", label: "24-hour clock (16:00)"}]
        current: bridge && bridge.clock24 ? "24" : "12"
        onPicked: (value) => page.bridge.setClock24(value === "24")
    }

    SectionTitle { theme: page.theme; text: "Week starts on" }
    ChipRow {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupWeekStart"
        accessPrefix: "Week starts on "
        choices: [{value: "monday", label: "Monday"}, {value: "sunday", label: "Sunday"}]
        current: bridge ? bridge.weekStart : "monday"
        onPicked: (value) => page.bridge.setWeekStart(value)
    }
    HelpText { theme: page.theme; width: parent.width; text: "The Week view always runs Monday to Sunday." }

    SectionTitle { theme: page.theme; text: "School" }
    DayChips {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupSchoolDay"
        accessPrefix: "School on "
        names: bridge ? bridge.dayNames : []
        days: bridge ? bridge.schoolDays : []
        onToggled: (day) => page.bridge.toggleSchoolDay(day)
    }
    Row {
        spacing: 12
        AccountField {
            objectName: "setupSchoolStart"
            width: 132
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            ground: palette.surface
            label: "Starts"
            accessName: "School starts"
            text: bridge ? bridge.schoolStart : ""
            onCommitted: (value) => page.bridge.setSchoolStart(value)
        }
        AccountField {
            objectName: "setupSchoolEnd"
            width: 132
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            ground: palette.surface
            label: "Ends"
            accessName: "School ends"
            text: bridge ? bridge.schoolEnd : ""
            onCommitted: (value) => page.bridge.setSchoolEnd(value)
        }
    }
    HelpText {
        objectName: "setupSchoolHint"
        theme: page.theme
        width: parent.width
        visible: bridge ? bridge.schoolHint : false
        text: "No school days picked means no school on the calendar."
    }

    SectionTitle { theme: page.theme; text: "Sports, clubs and jobs" }
    Repeater {
        model: bridge ? bridge.activitiesModel : null
        Rectangle {
            id: activity
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
                Row {
                    width: parent.width
                    spacing: 12
                    AccountField {
                        objectName: "setupActivityName" + activity.index
                        width: parent.width - removeButton.width - 12
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "Name"
                        accessName: "Activity name"
                        placeholder: "Soccer, band, a job…"
                        text: activity.row.title
                        onEdited: (value) => page.bridge.setActivityTitle(activity.index, value)
                    }
                    Button {
                        id: removeButton
                        objectName: "setupActivityRemove" + activity.index
                        y: 8
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        kind: "outlined"
                        text: "Remove"
                        accessName: "Remove this activity"
                        onClicked: page.bridge.removeActivity(activity.index)
                    }
                }
                DayChips {
                    width: parent.width
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    prefix: "setupActivityDay" + activity.index + "-"
                    accessPrefix: "Activity on "
                    names: page.bridge.dayNames
                    days: activity.row.days
                    onToggled: (day) => page.bridge.toggleActivityDay(activity.index, day)
                }
                Flow {
                    width: parent.width
                    spacing: 12
                    AccountField {
                        objectName: "setupActivityStart" + activity.index
                        width: 132
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "Starts"
                        accessName: "Activity starts"
                        text: activity.row.start
                        onCommitted: (value) => page.bridge.setActivityStart(activity.index, value)
                    }
                    AccountField {
                        objectName: "setupActivityEnd" + activity.index
                        width: 132
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "Ends"
                        accessName: "Activity ends"
                        text: activity.row.end
                        onCommitted: (value) => page.bridge.setActivityEnd(activity.index, value)
                    }
                    SegmentedButton {
                        objectName: "setupActivityCategory" + activity.index
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        accessName: "Sports or Activity"
                        choices: [{value: "extra", label: "Activity"}, {value: "exercise", label: "Sports"}]
                        current: activity.row.category
                        onSelected: (value) => page.bridge.setActivityCategory(activity.index, value)
                    }
                }
            }
        }
    }
    Button {
        objectName: "setupAddActivity"
        visible: bridge ? bridge.canAddActivity : false
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        kind: "text"
        icon: "add"
        text: "Add a sport, club or job"
        onClicked: page.bridge.addActivity()
    }

    SectionTitle { theme: page.theme; text: "Bedtime" }
    HelpText { theme: page.theme; width: parent.width; text: "No homework after" }
    ChipRow {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupCutoff"
        accessPrefix: "No homework after "
        choices: bridge ? bridge.cutoffChoices : []
        current: bridge ? bridge.cutoff : ""
        onPicked: (value) => page.bridge.setCutoff(value)
    }
}
