import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "computerSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Group {
        ToggleRow {
            key: "startAtLogin"
            visible: !!page.st.showLogin
            title: "Launch FlexWeek at login"
            subtitle: "Open when you sign in to this computer."
            isOn: !!page.st.startAtLogin
            onFlipped: (value) => page.panel.setStartAtLogin(value)
        }
        ToggleRow {
            key: "shortcuts"
            title: "Keyboard shortcuts"
            subtitle: "P plans, Z undoes, 1 to 5 switch views. Off while you type."
            isOn: !!page.st.shortcuts
            onFlipped: (value) => page.panel.setShortcuts(value)
        }
        ToggleRow {
            key: "reduceMotion"
            visible: !!page.st.showMotion
            title: "Reduce motion"
            subtitle: "Stops transitions and animations."
            isOn: !!page.st.reduceMotion
            onFlipped: (value) => page.panel.setReduceMotion(value)
        }
    }
    Group {
        LinkRow {
            key: "account"
            title: "Account"
            subtitle: "Name, password and sign out."
            onClicked: page.panel.openAccount()
        }
        LinkRow {
            key: "setup"
            title: "Run setup again"
            subtitle: "Go through the first-run questions."
            onClicked: page.panel.runSetup()
        }
        LinkRow {
            key: "updates"
            title: "Check for updates"
            subtitle: page.st.version || ""
            onClicked: page.panel.checkUpdates()
        }
    }
    Group {
        LinkRow {
            key: "pair"
            title: "Pair a phone"
            subtitle: page.st.pairCode ? "Enter this code on the phone: " + page.st.pairCode : "Show a code to link a phone."
            trailing: ""
            onClicked: page.panel.pair()
        }
        SettingsRow {
            visible: (page.st.phones || []).length > 0
            title: "Linked phones"
            subtitle: (page.st.phones || []).join(", ")
            objectName: "row_phones"
        }
        SettingsRow {
            visible: !!page.st.pairError
            title: "Pairing"
            subtitle: page.st.pairError || ""
            objectName: "row_pairError"
        }
    }
}
