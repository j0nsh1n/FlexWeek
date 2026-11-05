import QtQuick
import QtQuick.Layouts
import components 1.0

// The recovery codes a new account gets once. Continue stays off until the student says they saved them.
FocusScope {
    id: root
    objectName: "recoveryCard"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false

    M3Palette { id: palette; theme: root.theme }

    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, card.implicitHeight + 48)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Rectangle {
            id: card
            objectName: "recoverySurface"
            width: root.phone ? parent.width - 32 : 480
            x: (scroller.width - width) / 2
            y: Math.max(24, (scroller.height - implicitHeight) / 2)
            implicitHeight: column.implicitHeight + 64
            height: implicitHeight
            radius: 8
            color: palette.surfaceContainerLow
            border.width: root.highContrast ? 1.5 : 0
            border.color: palette.outline

            ColumnLayout {
                id: column
                x: 32
                y: 32
                width: parent.width - 64
                spacing: 16

                Text {
                    objectName: "authHeading"
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.heading : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 24
                    Accessible.role: Accessible.Heading
                    Accessible.name: text
                }
                Text {
                    objectName: "authNote"
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.note : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 14
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: codes.implicitHeight + 32
                    radius: 12
                    color: palette.surfaceContainerHighest
                    Text {
                        id: codes
                        objectName: "recoveryList"
                        x: 16
                        y: 16
                        width: parent.width - 32
                        text: bridge ? bridge.recoveryCodes : ""
                        color: palette.inkSurface
                        font.family: "monospace"
                        font.pixelSize: 16
                        font.weight: 500
                        lineHeight: 1.4
                        wrapMode: Text.WrapAnywhere
                        textFormat: Text.PlainText
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Recovery codes: " + text.replace(/\n/g, ", ")
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12
                    Button {
                        objectName: "recoveryCopy"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.copyLabel : "Copy"
                        accessName: "Copy recovery codes"
                        onClicked: bridge.copyCodes()
                    }
                    Button {
                        objectName: "recoverySave"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: bridge ? bridge.saveLabel : "Save…"
                        accessName: "Save recovery codes to a file"
                        onClicked: bridge.saveCodes()
                    }
                }
                Text {
                    objectName: "recoveryStatus"
                    Layout.fillWidth: true
                    visible: text !== ""
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.recoveryStatus : ""
                    wrapMode: Text.WordWrap
                    color: palette.error
                    font.family: M3Font.family
                    font.pixelSize: 14
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Switch {
                        id: ack
                        objectName: "recoveryAck"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        checked: bridge ? bridge.recoveryAck : false
                        accessName: bridge ? bridge.recoveryAckLabel : "I have saved these codes"
                        onToggled: (on) => bridge.setRecoveryAck(on)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: bridge ? bridge.recoveryAckLabel : ""
                        wrapMode: Text.WordWrap
                        color: palette.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: 14
                        font.weight: 500
                        MouseArea {
                            anchors.fill: parent
                            onClicked: bridge.setRecoveryAck(!ack.checked)
                        }
                    }
                }

                Button {
                    objectName: "recoveryContinue"
                    Layout.fillWidth: true
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "filled"
                    text: bridge ? bridge.recoveryContinueLabel : "Continue to my week"
                    enabled: bridge ? bridge.recoveryReady : false
                    onClicked: bridge.finishRecovery()
                }
                Text {
                    Layout.fillWidth: true
                    visible: bridge && !bridge.recoveryReady && !bridge.recoveryAck
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.recoveryWait : ""
                    color: palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 12
                }
            }
        }
    }
}
