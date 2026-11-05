import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string title: ""
    property string subtitle: ""
    property bool showDivider: false
    property bool interactive: false
    property bool settingsRow: true
    property string accessName: ""
    default property alias control: slot.data
    signal clicked()

    readonly property int padV: density === "compact" ? 10 : 16
    readonly property int contentHeight: titleText.implicitHeight + (subtitle === "" ? 0 : subtitleText.implicitHeight)
    implicitHeight: Math.max(56, contentHeight + padV * 2)
    height: implicitHeight
    implicitWidth: 360

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Rectangle {
        visible: root.showDivider
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }

    Text {
        id: titleText
        objectName: "title"
        x: 16
        y: root.padV + Math.max(0, (root.height - root.padV * 2 - root.contentHeight) / 2)
        width: Math.max(0, root.width - 32 - slot.width - (slot.width > 0 ? 16 : 0))
        text: root.title
        color: palette.inkSurface
        font.family: M3Font.family
        font.pixelSize: 16
        font.weight: 500
        lineHeight: 24
        lineHeightMode: Text.FixedHeight
        elide: Text.ElideRight
    }
    Text {
        id: subtitleText
        objectName: "subtitle"
        x: 16
        y: titleText.y + titleText.implicitHeight
        width: titleText.width
        visible: root.subtitle !== ""
        text: root.subtitle
        color: palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: 14
        font.weight: 400
        lineHeight: 20
        lineHeightMode: Text.FixedHeight
        elide: Text.ElideRight
    }
    Item {
        id: slot
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        width: childrenRect.width
        height: Math.max(childrenRect.height, 1)
    }

    M3StateLayer {
        anchors.fill: parent
        color: palette.inkSurface
        hovered: root.interactive && hover.hovered && root.enabled
        down: root.interactive && (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        objectName: "focusRing"
        anchors.fill: parent
        anchors.margins: -4
        extra: root.interactive
        ring: palette.focusRing
        ringRadius: 12
    }

    HoverHandler { id: hover; enabled: root.enabled && root.interactive }
    TapHandler {
        id: tap
        enabled: root.enabled && root.interactive
        onTapped: root.clicked()
    }
    activeFocusOnTab: interactive
    Accessible.role: interactive ? Accessible.Button : Accessible.StaticText
    Accessible.name: accessName !== "" ? accessName : title
    Accessible.description: subtitle
    Accessible.onPressAction: if (root.interactive && root.enabled) root.clicked()
    Keys.onPressed: (event) => {
        if (!root.interactive || !root.enabled)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (!root.interactive)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown && root.enabled)
                root.clicked()
            root.keyDown = false
            event.accepted = true
        }
    }
}
