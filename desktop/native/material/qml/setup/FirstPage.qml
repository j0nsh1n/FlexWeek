import QtQuick
import QtQuick.Layouts
import components 1.0
import "../account"

// Up to three pieces of homework, so the first week has something in it.
Column {
    id: page
    objectName: "setupFirstPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 12

    M3Palette { id: palette; theme: page.theme }

    Repeater {
        model: bridge ? bridge.homeworkModel : null
        Rectangle {
            id: item
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
                        objectName: "setupHomeworkName" + item.index
                        width: parent.width - removeButton.width - 12
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        label: "Name"
                        accessName: "Homework name"
                        placeholder: "e.g. History essay"
                        text: item.row.title
                        onEdited: (value) => page.bridge.setHomeworkTitle(item.index, value)
                    }
                    Button {
                        id: removeButton
                        objectName: "setupHomeworkRemove" + item.index
                        y: 8
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        kind: "outlined"
                        text: "Remove"
                        accessName: "Remove this homework"
                        onClicked: page.bridge.removeHomeworkRow(item.index)
                    }
                }
                HelpText { theme: page.theme; width: parent.width; text: "Takes" }
                ChipRow {
                    width: parent.width
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    prefix: "setupHomeworkMinutes" + item.index
                    accessPrefix: "Takes "
                    choices: page.bridge.lengthChoices
                    current: item.row.minutes
                    onPicked: (value) => page.bridge.setHomeworkMinutes(item.index, value)
                }
                HelpText { theme: page.theme; width: parent.width; text: "Due" }
                ChipRow {
                    width: parent.width
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    prefix: "setupHomeworkDue" + item.index
                    accessPrefix: "Due "
                    choices: page.bridge.dueChoices
                    current: item.row.due
                    onPicked: (value) => page.bridge.setHomeworkDue(item.index, value)
                }
                Row {
                    spacing: 12
                    Switch {
                        objectName: "setupHomeworkTimed" + item.index
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        checked: item.row.timed
                        accessName: "Due at a time"
                        onToggled: (on) => page.bridge.setHomeworkTimed(item.index, on)
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Due by a time of day"
                        color: palette.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: 14
                        font.weight: 500
                    }
                    AccountField {
                        objectName: "setupHomeworkTime" + item.index
                        visible: item.row.timed
                        width: 132
                        compact: true
                        theme: page.theme
                        density: page.density
                        reduceMotion: page.reduceMotion
                        highContrast: page.highContrast
                        accessName: "Due time"
                        text: item.row.time
                        onCommitted: (value) => page.bridge.setHomeworkTime(item.index, value)
                    }
                }
                HelpText {
                    theme: page.theme
                    width: parent.width
                    visible: item.row.timed
                    text: page.bridge.dueHint
                }
            }
        }
    }
    Button {
        objectName: "setupAddHomework"
        visible: bridge ? bridge.canAddHomework : false
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        kind: "text"
        icon: "add"
        text: "Add another"
        onClicked: page.bridge.addHomeworkRow()
    }
}
