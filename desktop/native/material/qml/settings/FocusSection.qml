import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "focusSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    readonly property bool any: !!(st.showPomodoro || st.showAudio || st.showSpotify)

    Text {
        objectName: "focusEmpty"
        visible: !page.any
        width: parent.width
        text: "No focus settings are available in this build yet."
        color: Ui.theme.onSurfaceVariant || "#44474e"
        font.family: M3Font.family
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
    Group {
        visible: page.any
        ToggleRow {
            key: "pomodoro"
            visible: !!page.st.showPomodoro
            title: "Pomodoro pacing"
            subtitle: "Focus in 25 minutes with 5 minute breaks."
            isOn: !!page.st.pomodoro
            onFlipped: (value) => page.panel.setPomodoro(value)
        }
        ChoiceRow {
            key: "focusAudio"
            visible: !!page.st.showAudio
            title: "Ambient focus audio"
            subtitle: "What plays when focus starts."
            choices: [
                { label: "Off", value: "off" },
                { label: "Rain", value: "rain" },
                { label: "Lo-Fi", value: "lo-fi" },
                { label: "White noise", value: "white-noise" },
                { label: "Spotify", value: "spotify" }
            ]
            current: page.st.focusAudio || "off"
            onChosen: (value) => page.panel.setFocusAudio(value)
        }
        FieldRow {
            key: "spotify"
            visible: !!page.st.showSpotify
            title: "Spotify link"
            subtitle: "Plays when focus starts and Spotify is the audio."
            placeholder: "https://open.spotify.com/playlist/..."
            text: page.st.spotify || ""
            error: page.st.spotifyError || ""
            onSubmitted: (value) => page.panel.setSpotify(value)
        }
    }
}
