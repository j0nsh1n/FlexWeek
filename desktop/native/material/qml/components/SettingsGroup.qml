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

    function mark() {
        var seen = 0
        for (var i = 0; i < column.children.length; i++) {
            var row = column.children[i]
            row.width = width
            if (row.showDivider === undefined)
                continue
            row.showDivider = seen > 0
            if (!row.theme)
                row.theme = root.theme
            row.density = root.density
            row.highContrast = root.highContrast
            row.reduceMotion = root.reduceMotion
            seen += 1
        }
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 16
        color: palette.surfaceContainerLow
        clip: true
        Column {
            id: column
            width: parent.width
            spacing: 0
            onChildrenChanged: root.mark()
            onImplicitHeightChanged: root.mark()
        }
    }

    onWidthChanged: mark()
    onDensityChanged: mark()
    onHighContrastChanged: mark()
    Component.onCompleted: mark()
}
