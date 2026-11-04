import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string title: ""
    property string subtitle: ""
    property string icon: ""
    property color bar: "transparent"
    property bool showBar: false
    // A tinted row (Day's category rows) sets both. Left alone, the row is the neutral one.
    property color fill: palette.surfaceContainerLow
    property color ink: "transparent"
    readonly property bool tinted: ink.a > 0
    property string accessName: ""
    // Room on the right for a tag or a check that sits on the row.
    property int trail: 0
    signal clicked()

    implicitHeight: Math.max(56, words.implicitHeight + 16)
    height: implicitHeight
    implicitWidth: 360

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 12
        color: root.fill
        border.width: root.highContrast ? 1.5 : 0
        border.color: palette.outline
    }
    Rectangle {
        visible: root.showBar
        width: 4
        height: parent.height
        color: root.bar
    }
    M3Icon {
        id: glyph
        x: 12
        y: (root.height - 24) / 2
        visible: root.icon !== ""
        name: root.icon
        width: 24
        height: 24
        color: root.tinted ? root.ink : palette.inkMuted
    }
    Column {
        id: words
        x: root.icon !== "" ? 48 : 12
        y: Math.max(8, (root.height - implicitHeight) / 2)
        width: Math.max(0, root.width - x - 12 - root.trail)
        spacing: 0
        Text {
            objectName: "title"
            width: parent.width
            text: root.title
            color: root.tinted ? root.ink : palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
            font.weight: 500
            elide: Text.ElideRight
        }
        Text {
            objectName: "subtitle"
            width: parent.width
            visible: root.subtitle !== ""
            text: root.subtitle
            color: root.tinted ? root.ink : palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: 12
            font.weight: 400
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
    M3StateLayer {
        anchors.fill: parent
        radius: 12
        color: palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: 16
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessName !== "" ? accessName : title
    Accessible.description: subtitle
    Accessible.onPressAction: if (root.enabled) root.clicked()
    Keys.onPressed: (event) => {
        if (!root.enabled)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown && root.enabled)
                root.clicked()
            root.keyDown = false
            event.accepted = true
        }
    }
}
