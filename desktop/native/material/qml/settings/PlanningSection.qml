import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "planningSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Group {
        // Kept on this computer, so it is always offered.
        GroupHeader { title: "Your week" }
        PickRow {
            key: "weekStart"
            title: "Week starts on"
            subtitle: "Week, Month and the date pickers start on this day."
            choices: [{ label: "Monday", value: "monday" }, { label: "Tuesday", value: "tuesday" },
                { label: "Wednesday", value: "wednesday" }, { label: "Thursday", value: "thursday" },
                { label: "Friday", value: "friday" }, { label: "Saturday", value: "saturday" },
                { label: "Sunday", value: "sunday" }]
            current: page.st.weekStart || "monday"
            onChosen: (value) => page.panel.setWeekStart(value)
        }
    }
    Group {
        visible: !!(page.st.showOpenOn || page.st.showPlanningStyle)
        GroupHeader { title: "Starting out" }
        ChoiceRow {
            key: "openOn"
            visible: !!page.st.showOpenOn
            title: "Open on"
            subtitle: "The screen FlexWeek starts on when you sign in."
            choices: page.st.openOnChoices || []
            current: page.st.openOn || "week"
            onChosen: (value) => page.panel.setOpenOn(value)
        }
        PickRow {
            key: "planningStyle"
            visible: !!page.st.showPlanningStyle
            title: "Planning style"
            subtitle: "When new homework gets a time."
            choices: page.st.planningStyleChoices || []
            current: page.st.planningStyle || "suggest"
            onChosen: (value) => page.panel.setPlanningStyle(value)
        }
        NoteRow {
            key: "planningStyleNote"
            visible: !!page.st.showPlanningStyle
            text: {
                const rows = page.st.planningStyleChoices || []
                for (let i = 0; i < rows.length; i++)
                    if (rows[i].value === page.st.planningStyle)
                        return rows[i].note
                return ""
            }
        }
    }
    Group {
        visible: !!(page.st.showWeekendFree || page.st.showBuffer || page.st.showUrgent || page.st.showSplit)
        GroupHeader { title: "How homework is planned" }
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
            subtitle: "Tasks over 60 minutes, other than homework, can divide into shorter sessions. Homework keeps its own In one go or Spread over days choice."
            isOn: !!page.st.split
            onFlipped: (value) => page.panel.setSplit(value)
        }
    }
    Group {
        GroupHeader { title: "Study hours" }
        ChoiceRow {
            key: "cutoff"
            visible: !!page.st.showCutoff
            title: "Study window cutoff"
            subtitle: "No homework planned after this hour."
            choices: page.st.cutoffChoices ? page.st.cutoffChoices : []
            current: page.st.cutoff || ""
            onChosen: (value) => page.panel.setCutoff(value)
        }
        StudyHoursEditor {}
    }
    Group {
        GroupHeader { title: "School hours" }
        SchoolHoursEditor {}
    }
    Group {
        visible: !!page.st.showDragStep
        GroupHeader { title: "Dragging" }
        ChoiceRow {
            key: "dragStep"
            visible: !!page.st.showDragStep
            title: "Dragging step"
            subtitle: "How far blocks move when you drag them and the times offered in lists."
            choices: [{ label: "5 min", value: "5" }, { label: "15 min", value: "15" }]
            current: String(page.st.dragStep === undefined ? 5 : page.st.dragStep)
            onChosen: (value) => page.panel.setDragStep(parseInt(value))
        }
    }
}
