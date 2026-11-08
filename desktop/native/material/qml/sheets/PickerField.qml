import QtQuick
import QtQuick.Controls
import components 1.0

// An outlined field that picks one of a list: a due date, a time of day, a category.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string label: ""
    property string accessName: ""
    // [{value, label}]
    property var options: []
    property var value
    property string placeholder: ""
    readonly property int count: options ? options.length : 0
    signal picked(var value)

    implicitHeight: 56
    height: 56
    implicitWidth: 200

    M3Palette { id: pal; theme: root.theme }

    function indexOfValue(v) {
        for (var i = 0; i < count; i++) {
            if (options[i].value === v)
                return i
        }
        return -1
    }
    readonly property int currentIndex: indexOfValue(value)
    readonly property string shown: currentIndex >= 0 ? options[currentIndex].label : placeholder

    function hostItem() {
        if (Overlay.overlay)
            return Overlay.overlay
        var win = root.Window.window
        return win ? win.contentItem : root
    }

    function openList() {
        if (!enabled || count === 0)
            return
        var host = hostItem()
        list.currentIndex = Math.max(0, currentIndex)
        var spot = root.mapToItem(host, 0, root.height)
        var room = host.height || 600
        var tall = Math.min(264, count * 44 + 16)
        popup.parent = host
        popup.width = root.width
        popup.height = tall
        popup.x = spot.x
        popup.y = spot.y + tall > room - 8 ? Math.max(8, spot.y - root.height - tall) : spot.y
        popup.open()
    }

    function choose(index) {
        if (index < 0 || index >= count)
            return
        value = options[index].value
        picked(value)
        popup.close()
        root.forceActiveFocus()
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        anchors.topMargin: 8
        radius: 6
        color: "transparent"
        // Material 3: focus thickens the field's own border in the accent; the label sits in its notch.
        border.width: root.activeFocus || popup.opened ? 2 : (root.highContrast ? 1.5 : 1)
        border.color: !root.enabled ? pal.disabledInk : (root.activeFocus || popup.opened ? pal.primary : pal.outline)
    }
    Rectangle {
        visible: root.label !== ""
        x: 12
        y: 0
        width: labelText.implicitWidth + 8
        height: 16
        color: pal.surfaceContainerHigh
        Text {
            id: labelText
            anchors.centerIn: parent
            text: root.label
            color: root.activeFocus || popup.opened ? pal.primary : (root.enabled ? pal.inkMuted : pal.disabledInk)
            font.family: M3Font.family
            font.pixelSize: 12
            font.weight: 400
        }
    }
    Text {
        objectName: "pickerValue"
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.right: chevron.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 4
        text: root.shown
        elide: Text.ElideRight
        color: root.enabled ? (root.currentIndex >= 0 ? pal.inkSurface : pal.inkMuted) : pal.disabledInk
        font.family: M3Font.family
        font.pixelSize: 16
        font.weight: 400
    }
    SIcon {
        id: chevron
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 4
        name: "expand_more"
        color: root.enabled ? pal.inkMuted : pal.disabledInk
    }
    M3StateLayer {
        anchors.fill: shape
        radius: 6
        color: pal.inkSurface
        hovered: hover.hovered && root.enabled
        down: tap.pressed && root.enabled
        reduceMotion: root.reduceMotion
    }
    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: { root.forceActiveFocus(); root.openList() } }

    activeFocusOnTab: true
    Accessible.role: Accessible.ComboBox
    Accessible.name: (accessName !== "" ? accessName : label) + ", " + shown
    Accessible.onPressAction: root.openList()
    Keys.onPressed: (event) => {
        if (!root.enabled)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                || event.key === Qt.Key_Down) {
            root.openList()
            event.accepted = true
        }
    }

    Popup {
        id: popup
        padding: 8
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 4
            color: pal.surfaceContainer
            border.width: root.highContrast ? 1.5 : 0
            border.color: pal.outline
        }
        onClosed: root.forceActiveFocus()
        contentItem: ListView {
            id: list
            objectName: "pickerList"
            clip: true
            model: root.options
            currentIndex: 0
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: true
            highlightMoveDuration: 0
            Keys.priority: Keys.BeforeItem
            Keys.onTabPressed: (event) => { event.accepted = true }
            Keys.onBacktabPressed: (event) => { event.accepted = true }
            delegate: Item {
                id: row
                width: list.width
                height: 44
                readonly property bool chosen: modelData.value === root.value
                Rectangle {
                    anchors.fill: parent
                    color: row.chosen ? pal.secondaryContainer
                        : (hoverRow.hovered || ListView.isCurrentItem
                            ? Qt.rgba(pal.inkSurface.r, pal.inkSurface.g, pal.inkSurface.b, 0.08) : "transparent")
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 16
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    elide: Text.ElideRight
                    color: row.chosen ? pal.inkSecondaryContainer : pal.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: row.chosen ? 500 : 400
                }
                HoverHandler { id: hoverRow }
                TapHandler { onTapped: root.choose(index) }
            }
            Keys.onReturnPressed: root.choose(currentIndex)
            Keys.onEnterPressed: root.choose(currentIndex)
            Keys.onSpacePressed: root.choose(currentIndex)
        }
    }
}
