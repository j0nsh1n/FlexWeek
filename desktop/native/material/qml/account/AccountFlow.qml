import QtQuick
import components 1.0
import "../setup"

// Covers the shell while the student is signing in, saving recovery codes, or in first-run setup.
// The window decides when; this only draws what the account bridge says.
FocusScope {
    id: root
    objectName: "accountFlow"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    readonly property bool phone: width < 640
    readonly property string phase: bridge ? bridge.phase : "app"

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        anchors.fill: parent
        color: palette.surface
    }

    Loader {
        id: loader
        anchors.fill: parent
        focus: true
        sourceComponent: root.phase === "setup" ? setupFlow : (root.phase === "recovery" ? recoveryCard : authCard)
        onLoaded: item.forceActiveFocus()
    }
    Component {
        id: authCard
        AuthCard {
            bridge: root.bridge
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            phone: root.phone
        }
    }
    Component {
        id: recoveryCard
        RecoveryCard {
            bridge: root.bridge
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            phone: root.phone
        }
    }
    Component {
        id: setupFlow
        SetupFlow {
            bridge: root.bridge
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            phone: root.phone
        }
    }

    // The shell's number and Z keys are not for these screens.
    Keys.onPressed: (event) => {
        if (event.key !== Qt.Key_Tab && event.key !== Qt.Key_Backtab)
            event.accepted = true
    }
}
