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
    property string suffix: ""
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
    readonly property color line: palette.outline

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        anchors.topMargin: 8
        radius: 6
        color: "transparent"
        // Material 3: focus thickens the field's own border in the accent; the label sits in its notch.
        border.width: input.activeFocus ? 2 : (root.highContrast ? 1.5 : 1)
        border.color: !root.enabled ? palette.disabledInk : (input.activeFocus ? palette.primary : palette.outline)
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
            font.pixelSize: M3Font.px(12)
            font.weight: 400
        }
    }
    TextInput {
        id: input
        objectName: "fieldInput"
        anchors.fill: parent
        anchors.topMargin: 8
        anchors.leftMargin: 16
        anchors.rightMargin: root.suffix !== "" ? 16 + suffixText.implicitWidth + 8 : 16
        verticalAlignment: TextInput.AlignVCenter
        text: root.text
        color: root.enabled ? palette.inkSurface : palette.disabledInk
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
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
    Text {
        id: suffixText
        visible: root.suffix !== ""
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.top: parent.top
        anchors.topMargin: 8
        anchors.bottom: parent.bottom
        verticalAlignment: Text.AlignVCenter
        text: root.suffix
        color: palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 400
    }

    Accessible.role: Accessible.EditableText
    Accessible.name: accessName !== "" ? accessName : label
    Accessible.editable: true
}
