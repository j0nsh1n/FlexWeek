import QtQuick
import components 1.0

// The focus timer as the whole window, as in the mockup's `?do=startFocus`. It only draws the
// session's timer (bridge.focus) and says what was pressed; the session does the rest.
Item {
    id: root
    objectName: "materialFocus"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // The shell clears `bridge` while the page is torn down. These stay readable then.
    readonly property var focusBridge: bridge ? bridge.focus : null
    readonly property bool shown: focusBridge ? focusBridge.open : false
    readonly property real scale: Math.max(0.5, Math.min(1, width / 700))

    visible: shown
    z: 10
    opacity: shown ? 1 : 0
    Accessible.role: Accessible.Dialog
    Accessible.name: "Focus"
    Behavior on opacity {
        NumberAnimation {
            duration: root.reduceMotion ? 0 : 300
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }

    M3Palette { id: palette; theme: root.theme }

    onShownChanged: if (shown) Qt.callLater(function() { actions.takeFocus() })

    Rectangle {
        anchors.fill: parent
        color: palette.surface
    }

    // Swallow clicks so the rail and FAB underneath do not act.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
    }

    // Keys that belong to this screen only. The shell's number keys and Z are off while it is open.
    Keys.onEscapePressed: (event) => {
        if (endDialog.open)
            endDialog.close()
        else if (focusBridge)
            focusBridge.back()
        event.accepted = true
    }
    focus: shown

    IconButton {
        id: backButton
        objectName: "focusBack"
        x: 12
        y: 12
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        icon: "arrow_back"
        accessName: "Back"
        onClicked: if (root.focusBridge) root.focusBridge.back()
    }

    Column {
        id: content
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 640)
        spacing: 12

        Text {
            objectName: "focusPhase"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.focusBridge ? root.focusBridge.phaseText : ""
            color: palette.primary
            font.family: M3Font.family
            font.pixelSize: 14
            font.weight: 500
            Accessible.role: Accessible.StaticText
            Accessible.name: "Focus phase " + text
        }

        Text {
            objectName: "focusTitle"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
            text: root.focusBridge ? root.focusBridge.title : ""
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 28
            font.weight: 400
            Accessible.role: Accessible.StaticText
            Accessible.name: "Task " + text
        }

        Text {
            objectName: "focusTime"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.focusBridge ? root.focusBridge.timeText : ""
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: Math.round(88 * root.scale)
            font.weight: 400
            font.features: { "tnum": 1 }
            Accessible.role: Accessible.StaticText
            Accessible.name: "Time left " + text
        }

        Text {
            objectName: "focusNote"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            height: 20
            text: root.focusBridge ? root.focusBridge.note : ""
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: 14
            font.weight: 400
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }

        Item {
            width: parent.width
            height: 24
        }

        Row {
            id: actions
            objectName: "focusActions"
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            function takeFocus() {
                var order = [start, pause, finished]
                for (var index = 0; index < order.length; index++) {
                    if (order[index].visible) {
                        order[index].forceActiveFocus()
                        return
                    }
                }
                backButton.forceActiveFocus()
            }

            Button {
                id: start
                objectName: "focusStart"
                visible: root.focusBridge ? root.focusBridge.ready : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                icon: "play_arrow"
                text: "Start"
                onClicked: root.focusBridge.begin()
            }

            Button {
                id: skip
                objectName: "focusSkip"
                visible: root.focusBridge ? root.focusBridge.active : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "outlined"
                text: "Skip"
                accessName: root.focusBridge ? root.focusBridge.skipHint : "Skip"
                onClicked: root.focusBridge.skip()
            }

            Button {
                id: pause
                objectName: "focusPause"
                visible: root.focusBridge ? root.focusBridge.active : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                icon: root.focusBridge && root.focusBridge.running ? "pause" : "play_arrow"
                text: root.focusBridge ? root.focusBridge.pauseText : "Pause"
                onClicked: root.focusBridge.togglePause()
            }

            Button {
                id: finish
                objectName: "focusFinish"
                visible: root.focusBridge ? root.focusBridge.active : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "tonal"
                text: "Finish"
                accessName: "Finish and end this session"
                onClicked: root.focusBridge.finish()
            }

            Button {
                id: finished
                objectName: "focusFinished"
                visible: root.focusBridge ? root.focusBridge.canFinishHomework : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Finished"
                accessName: "Mark this homework as finished"
                onClicked: root.focusBridge.markFinished()
            }

            Button {
                id: takeBreak
                objectName: "focusTakeBreak"
                visible: root.focusBridge ? root.focusBridge.ended : false
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "text"
                text: "Take a break"
                onClicked: root.focusBridge.takeBreak()
            }
        }
    }

    Dialog {
        id: endDialog
        objectName: "focusEndDialog"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        title: "End this session?"
        body: root.focusBridge ? root.focusBridge.endQuestion : ""
        confirmText: "End session"
        dismissText: "Keep going"
        onConfirmed: root.focusBridge.confirmEnd()
    }

    Connections {
        target: root.focusBridge
        function onEndRequested() { endDialog.open = true }
    }
}
