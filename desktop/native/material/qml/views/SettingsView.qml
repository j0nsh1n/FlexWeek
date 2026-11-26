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

    readonly property int minNavWidth: 72
    readonly property int maxNavWidth: Math.max(minNavWidth, Math.min(340, Math.floor(width * 0.38)))
    readonly property int rememberedNavWidth: st.navWidth ? st.navWidth : 220
    property int dragNavWidth: -1
    readonly property int navWidth: Math.max(minNavWidth, Math.min(maxNavWidth, dragNavWidth >= 0 ? dragNavWidth : rememberedNavWidth))

    M3Palette { id: m3; theme: Ui.theme }

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
        enabled: !root.st.askPreset && !root.st.prompt && !root.st.pairOpen

        SectionNav {
            id: nav
            objectName: "sectionNav"
            phone: root.phone
            anchors.left: parent.left
            anchors.top: parent.top
            width: root.phone ? parent.width : root.navWidth
            height: root.phone ? nav.wanted : parent.height
            current: root.st.section || "look"
            onPicked: (name) => root.panel.setSection(name)
        }

        // Draggable and keyboard-operable vertical divider resizing the Settings section list.
        Item {
            id: navDivider
            objectName: "settingsNavDivider"
            visible: !root.phone
            anchors.left: nav.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 10
            z: 2
            activeFocusOnTab: !root.phone
            Accessible.role: Accessible.Slider
            Accessible.name: "Resize settings sidebar"
            Accessible.description: "Section list width " + root.navWidth + " pixels. Use Left and Right arrow keys to resize"
            Accessible.onIncreaseAction: navDivider.stepResize(16)
            Accessible.onDecreaseAction: navDivider.stepResize(-16)

            function stepResize(delta) {
                if (!root.panel || !root.panel.setNavWidth)
                    return
                var next = Math.max(root.minNavWidth, Math.min(root.maxNavWidth, root.navWidth + delta))
                if (next !== root.navWidth)
                    root.panel.setNavWidth(next)
            }

            M3FocusRing {
                anchors.centerIn: parent
                width: 10
                height: 52
                ring: m3.focusRing
                ringRadius: 5
            }

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: m3.outlineVariant
            }
            Rectangle {
                anchors.centerIn: parent
                width: navDividerMouse.containsMouse || navDividerMouse.pressed || navDivider.activeFocus ? 4 : 2
                height: navDividerMouse.containsMouse || navDividerMouse.pressed || navDivider.activeFocus ? 40 : 24
                radius: width / 2
                color: navDividerMouse.containsMouse || navDividerMouse.pressed || navDivider.activeFocus ? m3.primary : m3.outlineVariant
            }

            Keys.onPressed: (event) => {
                var step = (event.modifiers & Qt.ShiftModifier) ? 40 : 16
                if (event.key === Qt.Key_Right) {
                    navDivider.stepResize(step)
                    event.accepted = true
                } else if (event.key === Qt.Key_Left) {
                    navDivider.stepResize(-step)
                    event.accepted = true
                } else if (event.key === Qt.Key_Home) {
                    navDivider.stepResize(root.minNavWidth - root.navWidth)
                    event.accepted = true
                } else if (event.key === Qt.Key_End) {
                    navDivider.stepResize(root.maxNavWidth - root.navWidth)
                    event.accepted = true
                }
            }

            MouseArea {
                id: navDividerMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.SplitHCursor
                property real pressSceneX: 0
                property int pressWidth: 220
                property bool moved: false
                onPressed: (mouse) => {
                    pressSceneX = mapToItem(root, mouse.x, 0).x
                    pressWidth = root.navWidth
                    moved = false
                }
                onPositionChanged: (mouse) => {
                    if (!pressed)
                        return
                    var curX = mapToItem(root, mouse.x, 0).x
                    var delta = curX - pressSceneX
                    var next = Math.max(root.minNavWidth, Math.min(root.maxNavWidth, Math.round(pressWidth + delta)))
                    if (Math.abs(delta) >= 1 && next !== pressWidth) {
                        moved = true
                        root.dragNavWidth = next
                    } else if (moved) {
                        root.dragNavWidth = next
                    }
                }
                onReleased: {
                    if (moved && root.dragNavWidth >= 0 && root.dragNavWidth !== pressWidth
                        && root.panel && root.panel.setNavWidth)
                        root.panel.setNavWidth(root.dragNavWidth)
                    moved = false
                    root.dragNavWidth = -1
                }
                onCanceled: {
                    moved = false
                    root.dragNavWidth = -1
                }
            }
        }

        Item {
            anchors.left: root.phone ? parent.left : navDivider.right
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
            Loader {
                id: syncLoader
                anchors.fill: parent
                active: root.st.section === "sync"
                visible: active
                sourceComponent: SyncSection {}
            }
        }
    }

    Loader {
        id: advanced
        anchors.fill: parent
        active: root.st.page === "advanced"
        sourceComponent: AdvancedPage {}
    }

    PairingDialog {
        theme: Ui.theme
        density: Ui.density
        reduceMotion: Ui.reduceMotion
        highContrast: Ui.highContrast
        phone: root.phone
        open: !!root.st.pairOpen
        code: root.st.pairCode || ""
        status: root.st.pairStatus || ""
        fraction: root.st.pairFraction === undefined ? 0.0 : root.st.pairFraction
        copied: !!root.st.pairCopied
        starting: !!root.st.pairStarting
        relayNote: root.st.relayNote || ""
        onCopyRequested: root.panel.copyPairCode()
        onRestartRequested: root.panel.pair()
        onDismissed: root.panel.closePairing()
        onClosed: Qt.callLater(function() {
            if (root.visible && root.st.section === "sync" && root.st.page === "sections"
                && syncLoader.item && syncLoader.item.pairRow)
                syncLoader.item.pairRow.forceActiveFocus()
        })
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

    Prompt {
        objectName: "removePhonePrompt"
        theme: Ui.theme
        density: Ui.density
        reduceMotion: Ui.reduceMotion
        highContrast: Ui.highContrast
        open: !!root.st.askRemove
        title: "Remove " + (root.st.removeName || "this phone") + "?"
        body: "The phone keeps its current data but won't sync with this computer anymore. Pair it again to reconnect."
        buttons: [
            { label: "Keep phone", value: "keep", kind: "text" },
            { label: "Remove phone", value: "remove", kind: "filled" }
        ]
        onPicked: (value, text) => root.panel.answerRemovePhone(value)
        onDismissed: root.panel.answerRemovePhone("keep")
    }

    Snackbar {
        objectName: "settingsNotice"
        visible: root.shownNotice !== "" && !root.st.prompt && !root.st.askPreset && !root.st.askRemove && !root.st.pairOpen
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
