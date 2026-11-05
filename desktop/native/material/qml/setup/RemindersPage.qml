import QtQuick
import QtQuick.Layouts
import components 1.0
import "../account"

// Reminders on or off, how long before, the alarm sound, and a test.
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

    SettingsGroup {
        width: parent.width
        theme: page.theme
        density: page.density
        reduceMotion: page.reduceMotion
        highContrast: page.highContrast
        SettingsRow {
            width: parent.width
            theme: page.theme
            density: page.density
            reduceMotion: page.reduceMotion
            highContrast: page.highContrast
            title: "Remind me before things start"
            Switch {
                objectName: "setupReminders"
                theme: page.theme
                density: page.density
                reduceMotion: page.reduceMotion
                highContrast: page.highContrast
                checked: bridge ? bridge.remindersOn : true
                accessName: "Remind me before things start"
                onToggled: (on) => page.bridge.setReminders(on)
            }
        }
    }
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
            width: page.width
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
