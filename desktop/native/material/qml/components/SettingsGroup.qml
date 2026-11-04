import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    default property alias rows: column.data

    implicitWidth: 480
    implicitHeight: column.implicitHeight
    width: implicitWidth
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    function _applyRow(item) {
        if (!item)
            return
        if ("theme" in item)
            item.theme = root.theme
        if ("density" in item)
            item.density = root.density
        if ("highContrast" in item)
            item.highContrast = root.highContrast
        if ("reduceMotion" in item)
            item.reduceMotion = root.reduceMotion
    }

    function mark() {
        var seen = 0
        for (var i = 0; i < column.children.length; i++) {
            var row = column.children[i]
            row.width = width
            if (row.showDivider !== undefined && row.visible) {
                row.showDivider = seen > 0
                seen += 1
            }
            _applyRow(row)
            if (row.children) {
                for (var j = 0; j < row.children.length; j++) {
                    _applyRow(row.children[j])
                }
            }
        }
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 16
        color: palette.surfaceContainerLow
        clip: false
        Column {
            id: column
            width: parent.width
            spacing: 0
            onChildrenChanged: root.mark()
            onImplicitHeightChanged: root.mark()
        }
    }

    onWidthChanged: mark()
    onVisibleChanged: mark()
    onThemeChanged: mark()
    onDensityChanged: mark()
    onHighContrastChanged: mark()
    onReduceMotionChanged: mark()
    Component.onCompleted: mark()
}
