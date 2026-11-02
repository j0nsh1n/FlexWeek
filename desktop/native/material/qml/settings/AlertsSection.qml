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
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
    Group {
        visible: !!page.st.showReminder
        ChoiceRow {
            key: "reminder"
            title: "Upcoming block reminders"
            subtitle: "How long before a block starts."
            choices: [{ label: "Off", value: "off" }, { label: "5m", value: "5" }, { label: "10m", value: "10" }, { label: "15m", value: "15" }]
            current: page.st.reminder || ""
            onChosen: (value) => page.panel.setReminder(value)
        }
    }
}
