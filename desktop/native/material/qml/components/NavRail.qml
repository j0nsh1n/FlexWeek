import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    default property alias destinations: slots.data

    implicitWidth: 80
    implicitHeight: 320
    width: 80

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        anchors.fill: parent
        color: palette.surfaceContainerLow
    }

    Item {
        id: slots
        anchors.fill: parent
        onChildrenChanged: root.place()
    }

    function place() {
        var rest = []
        var pinned = []
        for (var i = 0; i < slots.children.length; i++) {
            var child = slots.children[i]
            if (child.pinned)
                pinned.push(child)
            else
                rest.push(child)
        }
        var y = 12
        for (var r = 0; r < rest.length; r++) {
            var item = rest[r]
            item.x = (width - item.width) / 2
            item.y = y
            y += item.height + (item.railGap !== undefined ? item.railGap : 4)
        }
        var bottom = height - 12
        for (var p = pinned.length - 1; p >= 0; p--) {
            var foot = pinned[p]
            foot.x = (width - foot.width) / 2
            bottom -= foot.height
            foot.y = bottom
            bottom -= 4
        }
    }

    onWidthChanged: place()
    onHeightChanged: place()
    Component.onCompleted: place()
}
