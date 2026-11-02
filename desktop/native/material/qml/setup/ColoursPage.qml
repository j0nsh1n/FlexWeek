import QtQuick
import QtQuick.Layouts
import components 1.0

// Colours, text size, spacing, fine-tuning, and the day screen.
Column {
    id: page
    objectName: "setupColoursPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    property bool fine: false
    spacing: 12

    SectionTitle { theme: page.theme; text: "Colours" }
    ChipRow {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        prefix: "setupColour"
        accessPrefix: "Colours: "
        choices: {
            var rows = []
            var source = bridge ? bridge.colours : []
            for (var i = 0; i < source.length; i++)
                rows.push({value: source[i].value, label: source[i].label})
            return rows
        }
        current: {
            var source = bridge ? bridge.colours : []
            for (var i = 0; i < source.length; i++) {
                if (source[i].selected)
                    return source[i].value
            }
            return ""
        }
        onPicked: (value) => page.bridge.chooseColour(value)
    }

    Repeater {
        model: bridge ? bridge.knobsModel : null
        Column {
            id: knob
            required property var row
            width: page.width
            spacing: 8
            visible: row.key === "text" || row.key === "density" || page.fine
            SectionTitle { theme: page.theme; text: knob.row.label }
            ChipRow {
                width: parent.width
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                prefix: "setupKnob-" + knob.row.key
                accessPrefix: knob.row.label + ": "
                choices: knob.row.choices
                current: {
                    for (var i = 0; i < knob.row.choices.length; i++) {
                        if (knob.row.choices[i].selected)
                            return knob.row.choices[i].value
                    }
                    return ""
                }
                onPicked: (value) => page.bridge.chooseKnob(knob.row.key, value)
            }
        }
    }
    Button {
        objectName: "setupFineTune"
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        kind: "text"
        text: page.fine ? "Hide fonts and shadows" : "Fine-tune fonts and shadows"
        onClicked: page.fine = !page.fine
    }

    SectionTitle { theme: page.theme; text: "Day screen, for when you're doing the plan" }
    GridLayout {
        width: parent.width
        columns: page.phone || page.width < 620 ? 1 : 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.dayLayoutsModel : null
            ChoiceCard {
                required property var row
                Layout.fillWidth: true
                objectName: "setupDay-" + row.id
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: row.label
                note: row.note
                selected: row.selected
                onChosen: page.bridge.chooseDay(row.id)
            }
        }
    }
}
