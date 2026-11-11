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
            title: "Number keys"
            subtitle: "1 to 5 open Day, Week, Month, My day and Settings. Off while you type."
            isOn: !!page.st.shortcuts
            onFlipped: (value) => page.panel.setShortcuts(value)
        }
        ToggleRow {
            key: "letters"
            title: "Letter keys"
            subtitle: "P plans your homework, Z undoes and F opens Focus. Off while you type. Ctrl+Z undoes and Ctrl+Shift+Z or Ctrl+Y redoes with this on or off."
            isOn: !!page.st.letters
            onFlipped: (value) => page.panel.setLetterKeys(value)
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
        ToggleRow {
            objectName: "developerBuildsRow"
            visible: !!page.st.developerBuildsOffered
            key: "developerBuilds"
            title: "Get developer builds"
            subtitle: "Test builds with the newest fixes. They can have bugs."
            isOn: !!page.st.developerBuilds
            onFlipped: (value) => page.panel.setDeveloperBuilds(value)
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
