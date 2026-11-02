import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    default property alias destinations: slots.data

    implicitHeight: 80
    implicitWidth: 360
    height: 80

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        anchors.fill: parent
        color: palette.surfaceContainer
    }

    Item {
        id: slots
        anchors.fill: parent
        onChildrenChanged: root.place()
    }

    function place() {
        var items = slots.children
        if (items.length === 0)
            return
        var cell = width / items.length
        for (var n = 0; n < items.length; n++) {
            var item = items[n]
            item.bar = true
            item.width = cell
            item.height = 80
            item.x = n * cell
            item.y = 0
        }
    }

    onWidthChanged: place()
    onHeightChanged: place()
    Component.onCompleted: place()
}
