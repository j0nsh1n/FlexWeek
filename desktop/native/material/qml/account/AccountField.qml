import QtQuick
import components 1.0

// A text field for the account and setup screens: label on the border, a line of help or a problem
// under it, and for a password a Show/Hide button inside. The components' OutlinedField has neither
// a hidden entry nor a problem line, so this one wraps the same look.
FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string label: ""
    property string text: ""
    property string placeholder: ""
    property string hint: ""
    property string problem: ""
    property bool secret: false
    property bool revealed: false
    property bool compact: false
    property color ground: palette.surfaceContainerLow
    property string accessName: ""
    property int inputMethodHints: Qt.ImhNone
    property alias field: input
    signal edited(string value)
    signal committed(string value)
    signal submitted()

    M3Palette { id: palette; theme: root.theme }

    readonly property bool bad: problem !== ""
    readonly property color line: bad ? palette.error : palette.outline
    readonly property int boxHeight: compact ? 44 : 56

    implicitWidth: 280
    implicitHeight: boxHeight + 8 + (support.visible ? support.implicitHeight + 4 : 0)
    height: implicitHeight
    onActiveFocusChanged: {
        if (activeFocus && !input.activeFocus)
            input.forceActiveFocus()
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.left: parent.left
        anchors.right: parent.right
        y: 8
        height: root.boxHeight
        radius: 6
        color: "transparent"
        // Material 3: focus thickens the field's own border; the label sits in its notch.
        border.width: input.activeFocus ? 2 : (root.highContrast || root.bad ? 1.5 : 1)
        border.color: !root.enabled ? palette.disabledInk : (input.activeFocus && !root.bad ? palette.primary : root.line)
    }
    Rectangle {
        visible: root.label !== "" && !root.compact
        x: 12
        y: 0
        width: caption.implicitWidth + 8
        height: 16
        color: root.ground
        Text {
            id: caption
            anchors.centerIn: parent
            text: root.label
            color: root.bad ? palette.error : (input.activeFocus ? palette.primary : palette.inkMuted)
            font.family: M3Font.family
            font.pixelSize: 12
            font.weight: 400
        }
    }
    TextInput {
        id: input
        objectName: root.objectName + "Input"
        anchors.left: shape.left
        anchors.right: reveal.visible ? reveal.left : shape.right
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        y: shape.y
        height: shape.height
        verticalAlignment: TextInput.AlignVCenter
        text: root.text
        color: root.enabled ? palette.inkSurface : palette.disabledInk
        selectionColor: palette.primary
        selectedTextColor: palette.inkPrimary
        font.family: M3Font.family
        font.pixelSize: 16
        font.weight: 400
        echoMode: root.secret && !root.revealed ? TextInput.Password : TextInput.Normal
        inputMethodHints: root.inputMethodHints
        enabled: root.enabled
        clip: true
        selectByMouse: true
        activeFocusOnTab: true
        onTextEdited: root.edited(text)
        onEditingFinished: {
            root.committed(text)
            // A value the bridge refused goes back to what it holds.
            text = Qt.binding(function () { return root.text })
        }
        onAccepted: {
            root.committed(text)
            text = Qt.binding(function () { return root.text })
            root.submitted()
        }
        Accessible.role: Accessible.EditableText
        Accessible.name: root.accessName !== "" ? root.accessName : root.label
        Accessible.description: root.bad ? root.problem : root.hint
        Accessible.editable: true
        Text {
            visible: input.text === "" && !input.activeFocus
            anchors.verticalCenter: parent.verticalCenter
            text: root.placeholder
            color: palette.inkMuted
            font: input.font
            elide: Text.ElideRight
            width: parent.width
        }
    }
    Button {
        id: reveal
        objectName: root.objectName + "Reveal"
        visible: root.secret
        anchors.right: shape.right
        anchors.rightMargin: 4
        y: shape.y + (shape.height - height) / 2
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: root.revealed ? "Hide" : "Show"
        accessName: root.revealed ? "Hide password" : "Show password"
        onClicked: root.revealed = !root.revealed
    }
    Text {
        id: support
        objectName: root.objectName + "Support"
        visible: root.bad || root.hint !== ""
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        y: shape.y + shape.height + 4
        text: root.bad ? root.problem : root.hint
        wrapMode: Text.WordWrap
        color: root.bad ? palette.error : palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 400
    }
}
