import QtQuick
import components 1.0

// A title, a helper line and a segmented button. Under a narrow width the button drops below the text.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string key: ""
    property string title: ""
    property string subtitle: ""
    property var choices: []
    property string current: ""
    signal chosen(string value)
    objectName: "row_" + key

    readonly property int padV: density === "compact" ? 10 : 16
    readonly property int textHeight: 24 + (subtitle === "" ? 0 : 20)
    readonly property bool stacked: Math.max(titleText.implicitWidth, Math.min(subtitleText.implicitWidth, 240)) + seg.implicitWidth + 64 > width
    implicitHeight: stacked ? padV * 2 + textHeight + 8 + seg.height : Math.max(56, padV * 2 + textHeight)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Column {
        id: titleBlock
        x: 16
        y: root.padV
        width: root.stacked ? root.width - 32 : root.width - 32 - seg.width - 16
        Text {
            id: titleText
            width: parent.width
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: root.title
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
            font.weight: 500
            elide: Text.ElideRight
        }
        Text {
            id: subtitleText
            width: parent.width
            height: 20
            visible: root.subtitle !== ""
            verticalAlignment: Text.AlignVCenter
            text: root.subtitle
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: 14
            elide: Text.ElideRight
        }
    }
    SegmentedButton {
        id: seg
        objectName: root.key
        x: root.stacked ? 16 : root.width - width - 16
        y: root.stacked ? root.padV + root.textHeight + 8 : (root.height - height) / 2
        width: root.stacked ? Math.min(implicitWidth, Math.max(0, root.width - 32)) : implicitWidth
        height: implicitHeight
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        choices: root.choices
        current: root.current
        accessName: root.title
        onSelected: (value) => root.chosen(value)
    }
    onCurrentChanged: seg.current = current
    Connections {
        target: Ui.settings
        function onChanged() { seg.current = root.current }
    }
}
