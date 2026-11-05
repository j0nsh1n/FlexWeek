import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "planningSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    readonly property bool any: !!(st.showWeekendFree || st.showBuffer || st.showUrgent || st.showSplit || st.showCutoff)

    Text {
        objectName: "planningEmpty"
        visible: !page.any
        width: parent.width
        text: "No planning settings are available in this build yet."
        color: Ui.theme.onSurfaceVariant || "#44474e"
        font.family: M3Font.family
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
    Group {
        visible: page.any
        ToggleRow {
            key: "weekendFree"
            visible: !!page.st.showWeekendFree
            title: "Keep weekends homework-free"
            subtitle: "Plan homework on Monday to Friday only."
            isOn: !!page.st.weekendFree
            onFlipped: (value) => page.panel.setWeekendFree(value)
        }
        ChoiceRow {
            key: "buffer"
            visible: !!page.st.showBuffer
            title: "Smart buffer time"
            subtitle: "Breathing room between planned blocks."
            choices: [{ label: "None", value: "0" }, { label: "15m", value: "15" }, { label: "30m", value: "30" }]
            current: String(page.st.buffer === undefined ? 15 : page.st.buffer)
            onChosen: (value) => page.panel.setBuffer(parseInt(value))
        }
        ToggleRow {
            key: "urgent"
            visible: !!page.st.showUrgent
            title: "Prioritize urgent deadlines first"
            subtitle: "Tight work gets the earliest open slots."
            isOn: !!page.st.urgent
            onFlipped: (value) => page.panel.setUrgent(value)
        }
        ToggleRow {
            key: "split"
            visible: !!page.st.showSplit
            title: "Split long tasks"
            subtitle: "Tasks over 60 minutes can divide into shorter sessions."
            isOn: !!page.st.split
            onFlipped: (value) => page.panel.setSplit(value)
        }
        ChoiceRow {
            key: "cutoff"
            visible: !!page.st.showCutoff
            title: "Study window cutoff"
            subtitle: "No homework planned after this hour."
            choices: page.st.cutoffChoices ? page.st.cutoffChoices : []
            current: page.st.cutoff || ""
            onChosen: (value) => page.panel.setCutoff(value)
        }
    }
}
