import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "alertsSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Text {
        objectName: "alertsEmpty"
        visible: !page.st.showReminder
        width: parent.width
        text: "No alert settings are available in this build yet."
        color: Ui.theme.onSurfaceVariant || "#44474e"
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Group {
        visible: !!page.st.showReminder
        GroupHeader { title: "Reminders" }
        ChoiceRow {
            key: "reminder"
            title: "Upcoming block reminders"
            subtitle: "How long before a block starts."
            choices: page.st.reminderChoices && page.st.reminderChoices.length
                ? page.st.reminderChoices
                : [{ label: "Off", value: "off" }, { label: "5m", value: "5" }, { label: "10m", value: "10" }, { label: "15m", value: "15" }]
            current: page.st.reminder || ""
            onChosen: (value) => page.panel.setReminder(value)
        }
        ToggleRow {
            key: "reminderSound"
            title: "Play a sound"
            subtitle: "Reminders ring as well as show."
            isOn: !!page.st.reminderSound
            onFlipped: (value) => page.panel.setReminderSound(value)
        }
        PickRow {
            key: "alarmTone"
            title: "Sound"
            subtitle: "For reminders, the end of a focus session and new alarms."
            choices: page.st.toneChoices || []
            current: page.st.tone || "chime"
            onChosen: (value) => page.panel.setTone(value)
        }
        ActionRow {
            key: "playTone"
            title: "Hear it"
            subtitle: "Plays the sound at the volume below."
            buttonText: "Play"
            onActivated: page.panel.playTone()
        }
        FieldRow {
            key: "spotify"
            visible: !!page.st.showSpotify
            title: "Spotify link"
            subtitle: page.st.spotifyHint || ""
            placeholder: "https://open.spotify.com/playlist/..."
            text: page.st.spotify || ""
            error: page.st.spotifyError || ""
            onSubmitted: (value) => page.panel.setSpotify(value)
        }
        NoteRow {
            key: "toneNote"
            visible: !!page.st.toneNote
            text: page.st.spotifyRest || ""
        }
        ToggleRow {
            key: "dnd"
            title: "Leave reminders on screen"
            subtitle: page.st.dndNote || ""
            isOn: !!page.st.dnd
            onFlipped: (value) => page.panel.setDnd(value)
        }
    }
    Group {
        visible: !!page.st.showReminder
        GroupHeader { title: "While a session runs" }
        ToggleRow {
            key: "autoMute"
            title: "Mute alerts while a session runs"
            subtitle: "Reminders wait until the work part of a focus session is over."
            isOn: !!page.st.autoMute
            onFlipped: (value) => page.panel.setAutoMute(value)
        }
    }
    Group {
        visible: !!page.st.showReminder
        GroupHeader { title: "All alerts" }
        SliderRow {
            key: "volume"
            title: "Volume"
            unit: "%"
            from: 0
            to: 100
            step: 1
            value: page.st.volume === undefined ? 80 : page.st.volume
            onMoved: (value) => page.panel.setVolume(Math.round(value))
        }
        ToggleRow {
            key: "endChime"
            title: "Chime when a session ends"
            subtitle: "A short sound when the focus timer finishes."
            isOn: !!page.st.endChime
            onFlipped: (value) => page.panel.setEndChime(value)
        }
        ToggleRow {
            key: "tray"
            title: "Keep running when I close the window"
            subtitle: page.st.trayNote || ""
            isOn: !!page.st.tray
            onFlipped: (value) => page.panel.setTray(value)
        }
    }
}
