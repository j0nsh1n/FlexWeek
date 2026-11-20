import QtQuick
import QtQuick.Layouts
import components 1.0
import "../account"

// Reminders and the look: how long before things start, the colour preset, light or dark and the row size.
// The card that opens the sound options adds the number of minutes, the alarm sound, a Spotify link and a test.
Column {
    id: page
    objectName: "setupRemindersPage"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    spacing: 12

    M3Palette { id: palette; theme: page.theme }

    SectionTitle { theme: page.theme; text: "Remind me before things start" }
    GridLayout {
        width: parent.width
        columns: width >= 440 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.reminderCards : []
            ChoiceCard {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                objectName: "setupReminder-" + modelData.value
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: modelData.title
                note: modelData.note
                tag: modelData.tag
                selected: modelData.selected
                onChosen: page.bridge.setReminderChoice(modelData.value)
            }
        }
    }

    Button {
        objectName: "setupSoundOpen"
        visible: bridge ? !bridge.soundOpen : false
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        kind: "text"
        text: bridge ? bridge.soundCardTitle : ""
        onClicked: page.bridge.setSoundOpen(true)
    }

    Column {
        id: sound
        objectName: "setupSoundDetails"
        visible: bridge ? bridge.soundOpen : false
        width: parent.width
        spacing: 12

        Row {
            spacing: 12
            visible: bridge ? bridge.remindersOn : false
            AccountField {
                objectName: "setupLead"
                width: 160
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                ground: palette.surface
                label: "Minutes before"
                accessName: "How long before"
                text: bridge ? String(bridge.lead) : "10"
                inputMethodHints: Qt.ImhDigitsOnly
                onCommitted: (value) => {
                    var minutes = parseInt(value)
                    if (!isNaN(minutes))
                        page.bridge.setLead(minutes)
                }
            }
        }

        SectionTitle { theme: page.theme; text: "Alarm sound" }
        Repeater {
            model: bridge ? bridge.tones : []
            Row {
                id: tone
                required property var modelData
                width: sound.width
                spacing: 8
                ChoiceCard {
                    objectName: "setupTone-" + tone.modelData.value
                    width: parent.width - (tone.modelData.value === "spotify" ? 0 : playButton.width + 8)
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    title: tone.modelData.label
                    selected: page.bridge.tone === tone.modelData.value
                    onChosen: page.bridge.setTone(tone.modelData.value)
                }
                Button {
                    id: playButton
                    objectName: "setupPlay-" + tone.modelData.value
                    visible: tone.modelData.value !== "spotify"
                    anchors.verticalCenter: undefined
                    y: 12
                    theme: page.theme
                    density: page.density
                    reduceMotion: page.reduceMotion
                    highContrast: page.highContrast
                    kind: "tonal"
                    text: "Play"
                    accessName: "Play " + tone.modelData.label
                    onClicked: page.bridge.playTone(tone.modelData.value)
                }
            }
        }
        AccountField {
            objectName: "setupSpotify"
            width: parent.width
            visible: bridge ? bridge.spotifyOn : false
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            ground: palette.surface
            label: "Spotify link"
            accessName: "Spotify link"
            placeholder: bridge ? bridge.spotifyPlaceholder : ""
            text: bridge ? bridge.spotify : ""
            onEdited: (value) => page.bridge.setSpotify(value)
        }
        HelpText {
            theme: page.theme
            width: parent.width
            visible: bridge ? bridge.spotifyOn : false
            text: bridge ? bridge.spotifyNote : ""
        }
        Flow {
            width: parent.width
            spacing: 8
            Button {
                objectName: "setupTest"
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                kind: "text"
                text: "Send a test reminder"
                onClicked: page.bridge.sendTest()
            }
            Button {
                objectName: "setupSoundClose"
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                kind: "text"
                text: "Use the default sound"
                onClicked: page.bridge.useDefaultSound()
            }
        }
        HelpText {
            objectName: "setupTestResult"
            theme: page.theme
            width: parent.width
            visible: text !== ""
            text: bridge ? bridge.testResult : ""
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
    }

    SectionTitle { theme: page.theme; text: "Colour preset" }
    HelpText { theme: page.theme; width: parent.width; text: "Colours for the whole app." }
    Flow {
        objectName: "setupPresets"
        width: parent.width
        spacing: 16
        Repeater {
            model: bridge ? bridge.lookPresets : []
            PresetSwatch {
                required property var modelData
                objectName: "setupPreset-" + modelData.name
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                label: modelData.name
                selected: modelData.name === page.bridge.lookPreset
                quadrantPrimary: modelData.primary
                quadrantTertiary: modelData.tertiary
                quadrantSecondary: modelData.secondaryContainer
                quadrantPrimaryContainer: modelData.primaryContainer
                onClicked: page.bridge.setLookPreset(modelData.name)
            }
        }
    }

    SectionTitle { theme: page.theme; text: "Light or dark" }
    GridLayout {
        width: parent.width
        columns: width >= 440 ? 3 : 1
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.lookModes : []
            ChoiceCard {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                objectName: "setupMode-" + modelData.value
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: modelData.title
                note: modelData.note
                selected: modelData.selected
                enabled: modelData.enabled
                opacity: enabled ? 1 : 0.5
                onChosen: page.bridge.setLookMode(modelData.value)
            }
        }
    }

    SectionTitle { theme: page.theme; text: "Row size" }
    GridLayout {
        width: parent.width
        columns: width >= 440 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: bridge ? bridge.rowSizes : []
            ChoiceCard {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                objectName: "setupRowSize-" + modelData.value
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                title: modelData.title
                note: modelData.note
                selected: modelData.selected
                onChosen: page.bridge.setLookDensity(modelData.value)
            }
        }
    }
}
