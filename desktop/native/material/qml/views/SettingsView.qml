import QtQuick
import components 1.0
import settings 1.0

Item {
    id: root
    objectName: "materialSettings"
    property var bridge
    readonly property var panel: bridge ? bridge.settingsBridge : null
    readonly property var st: Ui.st
    readonly property bool phone: width < 768
    property string shownNotice: ""

    Binding { target: Ui; property: "bridge"; value: root.bridge }
    Binding { target: Ui; property: "settings"; value: root.panel }
    Binding { target: Ui; property: "theme"; value: root.bridge ? root.bridge.theme : ({}) }
    Binding { target: Ui; property: "density"; value: root.bridge ? root.bridge.density : "comfortable" }
    Binding { target: Ui; property: "reduceMotion"; value: root.bridge ? root.bridge.reduceMotion : false }
    Binding { target: Ui; property: "highContrast"; value: root.bridge ? root.bridge.highContrast : false }
    Binding { target: Ui; property: "phone"; value: root.phone }

    // The top bar already shows the word. This is the page's heading for a screen reader.
    Text {
        objectName: "screenTitle"
        width: 0
        height: 0
        clip: true
        text: "Settings"
        Accessible.role: Accessible.Heading
        Accessible.name: "Settings"
    }

    Item {
        id: sections
        objectName: "settingsSections"
        anchors.fill: parent
        visible: root.st.page !== "advanced"

        SectionNav {
            id: nav
            objectName: "sectionNav"
            phone: root.phone
            anchors.left: parent.left
            anchors.top: parent.top
            width: root.phone ? parent.width : 220
            height: root.phone ? nav.wanted : parent.height
            current: root.st.section || "look"
            onPicked: (name) => root.panel.setSection(name)
        }
        Item {
            anchors.left: root.phone ? parent.left : nav.right
            anchors.right: parent.right
            anchors.top: root.phone ? nav.bottom : parent.top
            anchors.bottom: parent.bottom
            Loader {
                anchors.fill: parent
                active: (root.st.section || "look") === "look"
                visible: active
                sourceComponent: LookSection {}
            }
            Loader {
                anchors.fill: parent
                active: root.st.section === "planning"
                visible: active
                sourceComponent: PlanningSection {}
            }
            Loader {
                anchors.fill: parent
                active: root.st.section === "focus"
                visible: active
                sourceComponent: FocusSection {}
            }
            Loader {
                anchors.fill: parent
                active: root.st.section === "alerts"
                visible: active
                sourceComponent: AlertsSection {}
            }
            Loader {
                anchors.fill: parent
                active: root.st.section === "computer"
                visible: active
                sourceComponent: ComputerSection {}
            }
        }
    }

    Loader {
        id: advanced
        anchors.fill: parent
        active: root.st.page === "advanced"
        sourceComponent: AdvancedPage {}
    }

    Prompt {
        objectName: "presetPrompt"
        theme: Ui.theme
        density: Ui.density
        reduceMotion: Ui.reduceMotion
        highContrast: Ui.highContrast
        open: !!root.st.askPreset
        title: "Keep your advanced changes?"
        body: "You changed advanced dials on top of " + (root.st.preset || "this") + ". Keep them on "
              + (root.st.pendingPreset || "the new preset") + ", or start from its own look?"
        buttons: [
            { label: "Cancel", value: "cancel", kind: "text" },
            { label: "Start fresh", value: "discard", kind: "tonal" },
            { label: "Keep them", value: "keep", kind: "filled" }
        ]
        onPicked: (value, text) => root.panel.answerPreset(value)
        onDismissed: root.panel.answerPreset("cancel")
    }

    Snackbar {
        objectName: "settingsNotice"
        visible: root.shownNotice !== "" && !root.st.prompt && !root.st.askPreset
        z: 10
        message: root.shownNotice
        actionText: ""
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        theme: Ui.theme
        density: Ui.density
        reduceMotion: Ui.reduceMotion
        highContrast: Ui.highContrast
    }
    Timer {
        id: noticeTimer
        interval: 4000
        onTriggered: root.shownNotice = ""
    }
    Connections {
        target: root.panel
        function onChanged() {
            var text = root.st.notice || ""
            if (text !== "" && text !== root.shownNotice) {
                root.shownNotice = text
                noticeTimer.restart()
            }
        }
    }
}
