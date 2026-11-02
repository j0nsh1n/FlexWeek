import QtQuick

FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string label: "Label"
    property string text: ""
    property string placeholder: ""
    property string accessName: ""
    signal textEdited(string value)

    implicitHeight: 56
    height: 56
    implicitWidth: 280
    activeFocusOnTab: true
    onActiveFocusChanged: {
        if (activeFocus && !input.activeFocus)
            input.forceActiveFocus()
    }

    M3Palette { id: palette; theme: root.theme }
    readonly property color line: input.activeFocus ? palette.primary : palette.outline

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        anchors.topMargin: 8
        radius: 4
        color: "transparent"
        border.width: root.highContrast || input.activeFocus ? 1.5 : 1
        border.color: root.enabled ? root.line : palette.disabledInk
    }
    Rectangle {
        visible: root.label !== ""
        x: 12
        y: 0
        width: labelText.implicitWidth + 8
        height: 16
        color: palette.surfaceContainerHigh
        Text {
            id: labelText
            anchors.centerIn: parent
            text: root.label
            color: input.activeFocus ? palette.primary : (root.enabled ? palette.inkMuted : palette.disabledInk)
            font.family: M3Font.family
            font.pixelSize: 12
            font.weight: 400
        }
    }
    TextInput {
        id: input
        objectName: "fieldInput"
        anchors.fill: parent
        anchors.topMargin: 8
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        verticalAlignment: TextInput.AlignVCenter
        text: root.text
        color: root.enabled ? palette.inkSurface : palette.disabledInk
        font.family: M3Font.family
        font.pixelSize: 16
        font.weight: 400
        enabled: root.enabled
        clip: true
        selectByMouse: true
        activeFocusOnTab: false
        onTextEdited: {
            root.text = text
            root.textEdited(text)
        }
        Text {
            visible: input.text === "" && !input.activeFocus
            anchors.verticalCenter: parent.verticalCenter
            text: root.placeholder
            color: palette.inkMuted
            font: input.font
        }
    }
    M3FocusRing {
        anchors.fill: shape
        anchors.margins: -4
        shown: input.activeFocus
        ring: palette.primary
        ringRadius: 8
    }

    Accessible.role: Accessible.EditableText
    Accessible.name: accessName !== "" ? accessName : label
    Accessible.editable: true
}
