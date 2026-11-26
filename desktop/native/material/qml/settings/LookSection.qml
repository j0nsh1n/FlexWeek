import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "lookSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Group {
        GroupHeader { title: "Colours" }
        PresetRow {
            subtitle: "Colours for the whole app."
            swatches: page.st.swatches || []
            current: page.st.preset || ""
            onChosen: (name) => page.panel.setPreset(name)
        }
        ChoiceRow {
            key: "accent"
            title: "Accent colour"
            subtitle: page.st.accentLocked
                ? "High contrast keeps its yellow."
                : "On top of the preset."
            choices: page.st.accentChoices || []
            current: page.st.accent || "default"
            onChosen: (value) => page.panel.setAccent(value)
        }
        ToggleRow {
            key: "accentChips"
            title: "Use the accent on category chips"
            subtitle: "Every category wears the accent instead of its own colour."
            isOn: !!page.st.accentChips
            onFlipped: (value) => page.panel.setAccentChips(value)
        }
    }
    Group {
        visible: !!page.st.showMotion
        GroupHeader { title: "Animations" }
        ChoiceRow {
            key: "animations"
            title: "Animations"
            subtitle: "How much moves when screens change. Reduce keeps only what you need to follow, Off stops it all."
            choices: page.st.animationChoices || []
            current: page.st.animations || "normal"
            onChosen: (value) => page.panel.setAnimations(value)
        }
    }
    Group {
        GroupHeader { title: "Light and dark" }
        ChoiceRow {
            key: "mode"
            title: "Mode"
            subtitle: page.st.oneMode === "dark"
                ? "This preset is a dark look, so it stays dark."
                : (page.st.oneMode === "light"
                    ? "This preset is a light look, so it stays light."
                    : "Follow this device, or choose.")
            // A one-mode preset shows the mode it is drawn in and leaves the other two off.
            choices: [
                { label: "Same as this computer", value: "system", enabled: !page.st.oneMode },
                { label: "Light", value: "light", enabled: !page.st.oneMode || page.st.oneMode === "light" },
                { label: "Dark", value: "dark", enabled: !page.st.oneMode || page.st.oneMode === "dark" }
            ]
            current: page.st.oneMode ? page.st.oneMode : (page.st.mode || "")
            onChosen: (value) => page.panel.setMode(value)
        }
        ChoiceRow {
            key: "contrast"
            title: "Contrast"
            subtitle: "Stronger lines and text."
            choices: [{ label: "Standard", value: "std" }, { label: "High", value: "high" }]
            current: page.st.contrast || ""
            onChosen: (value) => page.panel.setContrast(value)
        }
        ChoiceRow {
            key: "density"
            title: "Row size"
            subtitle: "How much fits on the screen."
            choices: [{ label: "Comfortable", value: "comfortable" }, { label: "Compact", value: "compact" }]
            current: page.st.density || ""
            onChosen: (value) => page.panel.setDensity(value)
        }
    }
    Group {
        GroupHeader { title: "Text" }
        ChoiceRow {
            key: "font"
            title: "Font"
            subtitle: "Sans is Inter. Serif is Newsreader headings over Inter. Mono is JetBrains Mono."
            choices: page.st.fontChoices || []
            current: page.st.font || "sans"
            onChosen: (value) => page.panel.setFont(value)
        }
        ChoiceRow {
            key: "textSize"
            title: "Text size"
            subtitle: "Scale text and rows."
            choices: [
                { label: "Small", value: "small" },
                { label: "Normal", value: "normal" },
                { label: "Large", value: "large" },
                { label: "Larger", value: "larger" }
            ]
            current: page.st.textSize || "normal"
            onChosen: (value) => page.panel.setTextSize(value)
        }
    }
    Group {
        visible: !!page.st.showWeekendsRow || !!page.st.showClock
        GroupHeader { title: "Calendar" }
        ToggleRow {
            key: "showWeekends"
            visible: !!page.st.showWeekendsRow
            title: "Show weekends"
            subtitle: "Sat and Sun columns in the week."
            isOn: !!page.st.showWeekends
            onFlipped: (value) => page.panel.setShowWeekends(value)
        }
        ToggleRow {
            key: "clock24"
            visible: !!page.st.showClock
            title: "Use 24-hour time"
            subtitle: "Show 15:40 rather than 3:40 PM."
            isOn: !!page.st.clock24
            onFlipped: (value) => page.panel.setClock(value)
        }
    }
    Group {
        visible: (page.st.savedNames || []).length > 0
        // Repeater as a Group child does not grow SettingsGroup: wrap it in a Column.
        Column {
            width: parent.width
            GroupHeader { title: "Saved looks" }
            Repeater {
                model: page.st.savedNames || []
                delegate: SettingsRow {
                    width: parent.width
                    title: modelData
                    subtitle: "Wear this look."
                    objectName: "row_saved_" + index
                    Row {
                        spacing: 8
                        Button {
                            objectName: "wearSaved_" + index
                            theme: Ui.theme
                            density: Ui.density
                            reduceMotion: Ui.reduceMotion
                            highContrast: Ui.highContrast
                            kind: "tonal"
                            text: "Apply"
                            accessName: "Apply " + modelData
                            onClicked: page.panel.useSaved(modelData)
                        }
                        Button {
                            objectName: "forgetSaved_" + index
                            theme: Ui.theme
                            density: Ui.density
                            reduceMotion: Ui.reduceMotion
                            highContrast: Ui.highContrast
                            kind: "text"
                            text: "Delete"
                            accessName: "Delete " + modelData
                            onClicked: page.panel.forgetSaved(modelData)
                        }
                    }
                }
            }
        }
    }
    property bool _wasAdvanced: false
    Connections {
        target: page.panel
        function onChanged() {
            if (page._wasAdvanced && page.st.page !== "advanced") {
                page._wasAdvanced = false
                openAdvanced.forceActiveFocus()
            } else if (page.st.page === "advanced") {
                page._wasAdvanced = true
            }
        }
    }

    Group {
        GroupHeader { title: "More" }
        LinkRow {
            id: openAdvanced
            key: "advanced"
            objectName: "openAdvanced"
            title: "Advanced settings"
            subtitle: "Corners, density, type, motion, depth and calendar dials, with a live preview."
            onClicked: page.panel.openAdvanced()
            onActiveFocusChanged: {
                if (activeFocus)
                    page.ensureVisible(this)
            }
        }
    }
}
