import QtQuick
import components 1.0

SectionPage {
    id: page
    objectName: "computerSection"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings

    Group {
        GroupHeader { title: "Startup & shortcuts"; icon: "computer" }
        ToggleRow {
            key: "startAtLogin"
            visible: !!page.st.showLogin
            title: "Open FlexWeek when I log in"
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
            subtitle: "T goes to today, D, W and M open Day, Week and Month, J and K go to the next and previous one, C adds homework, P plans your homework, Z undoes and F opens Focus. Off while you type. Ctrl+Z undoes and Ctrl+Shift+Z or Ctrl+Y redoes with this on or off."
            isOn: !!page.st.letters
            onFlipped: (value) => page.panel.setLetterKeys(value)
        }
    }
    Group {
        GroupHeader { title: "Account & updates"; icon: "verified_user" }
        LinkRow {
            key: "account"
            title: "Account"
            subtitle: "Name, password, recovery codes and your files."
            onClicked: page.panel.openAccount()
        }
        ActionRow {
            key: "signOut"
            title: "Sign out"
            subtitle: "Signed in as " + (page.st.accountName || "") + ". Your week is saved first."
            buttonText: "Sign out"
            buttonEnabled: !page.st.sessionBusy
            onActivated: page.panel.signOut()
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
        LinkRow {
            objectName: "reportProblemRow"
            visible: !!page.st.feedbackAvailable
            key: "report"
            title: "Report a problem"
            subtitle: "Opens a short form in your browser, with your FlexWeek version filled in."
            onClicked: page.panel.reportProblem()
        }
    }
}
