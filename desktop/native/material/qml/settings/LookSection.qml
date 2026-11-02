import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "lookSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Group {
        SettingsRow {
            objectName: "row_style"
            title: "Style"
            subtitle: "Material 3 · switch to the other styles"
            Button {
                objectName: "useWidgets"
                theme: Ui.theme
                density: Ui.density
                reduceMotion: Ui.reduceMotion
                highContrast: Ui.highContrast
                kind: "tonal"
                text: "Widgets styles"
                accessName: "Widgets styles"
                onClicked: Ui.bridge.useWidgets()
            }
        }
    }
    Group {
        PresetRow {
            subtitle: "Colours for the whole app."
            swatches: page.st.swatches || []
            current: page.st.preset || ""
            onChosen: (name) => page.panel.setPreset(name)
        }
    }
    Group {
        ChoiceRow {
            key: "mode"
            title: "Mode"
            subtitle: "Follow this device, or choose."
            choices: [{ label: "Auto", value: "system" }, { label: "Light", value: "light" }, { label: "Dark", value: "dark" }]
            current: page.st.mode || ""
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
            title: "Density"
            subtitle: "How much fits on the screen."
            choices: [{ label: "Comfortable", value: "comfortable" }, { label: "Compact", value: "compact" }]
            current: page.st.density || ""
            onChosen: (value) => page.panel.setDensity(value)
        }
    }
    Group {
        visible: !!page.st.showWeekendsRow || !!page.st.showClock
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
            title: "24-hour time"
            subtitle: "Show 15:40 rather than 3:40 PM."
            isOn: !!page.st.clock24
            onFlipped: (value) => page.panel.setClock(value)
        }
    }
    Group {
        visible: (page.st.savedNames || []).length > 0
        GroupHeader { title: "Saved looks" }
        Repeater {
            model: page.st.savedNames || []
            delegate: LinkRow {
                key: "saved_" + index
                title: modelData
                subtitle: "Wear this look."
                onClicked: page.panel.useSaved(modelData)
            }
        }
    }
    Group {
        LinkRow {
            key: "advanced"
            objectName: "openAdvanced"
            title: "Advanced settings"
            subtitle: "Corners, density, type, motion, depth and calendar dials, with a live preview."
            onClicked: page.panel.openAdvanced()
        }
    }
}
