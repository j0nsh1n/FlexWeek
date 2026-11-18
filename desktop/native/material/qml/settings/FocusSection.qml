import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "focusSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    readonly property bool any: !!(st.showPomodoro || st.showAudio)

    Text {
        objectName: "focusEmpty"
        visible: !page.any
        width: parent.width
        text: "No focus settings are available in this build yet."
        color: Ui.theme.onSurfaceVariant || "#44474e"
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Group {
        visible: !!page.st.showPomodoro
        GroupHeader { title: "Focus timer" }
        ChoiceRow {
            key: "timerPreset"
            title: "Timer"
            subtitle: "Pick a set of lengths, or Custom to set each one."
            choices: page.st.timerChoices || []
            current: page.st.timerPreset || "standard"
            onChosen: (value) => page.panel.setTimerPreset(value)
        }
        ToggleRow {
            key: "autoSplit"
            title: "Split long homework into focus sessions"
            subtitle: "Splitting needs lengths in steps of 15 minutes."
            isOn: !!page.st.autoSplit
            onFlipped: (value) => page.panel.setAutoSplit(value)
        }
        NoteRow {
            key: "timerNote"
            visible: (page.st.timerNote || "") !== ""
            text: page.st.timerNote || ""
        }
    }
    Group {
        objectName: "customTimer"
        visible: !!page.st.showPomodoro && page.st.timerPreset === "custom"
        GroupHeader { title: "Custom lengths" }
        SliderRow {
            key: "timerWork"
            title: "Focus minutes"
            unit: " min"
            from: page.st.timerFrom || 1
            to: 180
            step: page.st.timerStep || 1
            value: page.st.timerWork || 30
            onMoved: (value) => page.panel.setTimerLength("work", Math.round(value))
        }
        SliderRow {
            key: "timerBreak"
            title: "Break minutes"
            unit: " min"
            from: page.st.timerFrom || 1
            to: 60
            step: page.st.timerStep || 1
            value: page.st.timerBreak || 15
            onMoved: (value) => page.panel.setTimerLength("break", Math.round(value))
        }
        SliderRow {
            key: "timerLong"
            title: "Long break minutes"
            unit: " min"
            from: page.st.timerFrom || 1
            to: 120
            step: page.st.timerStep || 1
            value: page.st.timerLong || 30
            onMoved: (value) => page.panel.setTimerLength("long", Math.round(value))
        }
        SliderRow {
            key: "timerEvery"
            title: "Long break after"
            unit: " focus sessions"
            from: 2
            to: 12
            step: 1
            value: page.st.timerEvery || 4
            onMoved: (value) => page.panel.setTimerLength("every", Math.round(value))
        }
    }
    Group {
        visible: !!page.st.showAudio
        GroupHeader { title: "While you focus" }
        ChoiceRow {
            key: "focusAudio"
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
        NoteRow {
            key: "focusAudioNote"
            text: page.st.focusAudioNote || ""
        }
        ToggleRow {
            key: "autoComplete"
            title: "Mark homework finished when its session ends"
            subtitle: "The session's block moves to Done."
            isOn: !!page.st.autoComplete
            onFlipped: (value) => page.panel.setAutoComplete(value)
        }
    }
}
