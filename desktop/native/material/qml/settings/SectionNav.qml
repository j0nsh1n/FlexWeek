import QtQuick
import components 1.0

// The six section pills: a resizable column on a desktop (collapsing to centered icons when narrow),
// and a horizontal wrapping strip on a phone.
Item {
    id: root
    property string current: "look"
    property bool phone: false
    signal picked(string name)
    readonly property bool iconOnly: !phone && width < 140
    readonly property var sections: [
        { name: "look", label: "Look", icon: "palette" },
        { name: "planning", label: "Planning", icon: "event_note" },
        { name: "focus", label: "Focus", icon: "timer" },
        { name: "alerts", label: "Alerts", icon: "notifications" },
        { name: "computer", label: "This computer", icon: "computer" },
        { name: "sync", label: "Phone & sync", icon: "smartphone" }
    ]

    M3Palette { id: m3; theme: Ui.theme }

    readonly property real wanted: pillFlow.height + 16

    Rectangle {
        visible: !root.phone
        anchors.fill: parent
        color: m3.panelSurface
    }

    Flow {
        id: pillFlow
        x: root.iconOnly ? 10 : 12
        y: root.phone ? 8 : 14
        width: Math.max(0, root.width - (root.iconOnly ? 20 : 24))
        spacing: root.phone ? 8 : 4
        Repeater {
            id: pills
            model: root.sections
            delegate: Item {
                id: pill
                objectName: "section_" + modelData.name
                readonly property bool on: root.current === modelData.name
                width: root.phone
                    ? (iconGlyph.width + 8 + caption.implicitWidth + 28)
                    : (root.width - (root.iconOnly ? 20 : 24))
                height: root.phone ? 40 : 46
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.label
                Accessible.checkable: true
                Accessible.checked: on
                Accessible.onPressAction: root.picked(modelData.name)
                Rectangle {
                    anchors.fill: parent
                    radius: m3.cornerFor(pill.height / 2, pill.height / 2)
                    color: pill.on ? m3.secondaryContainer : "transparent"
                }
                M3StateLayer {
                    anchors.fill: parent
                    radius: m3.cornerFor(pill.height / 2, pill.height / 2)
                    color: m3.inkSurface
                    hovered: hover.hovered && !pill.on
                    down: tap.pressed
                    reduceMotion: Ui.reduceMotion
                }
                M3FocusRing {
                    anchors.fill: parent
                    anchors.margins: -4
                    ring: m3.focusRing
                    ringRadius: m3.cornerFor(parent.height / 2, parent.height / 2) + 4
                }
                M3Icon {
                    id: iconGlyph
                    name: modelData.icon
                    width: 20
                    height: 20
                    x: root.iconOnly ? (parent.width - width) / 2 : 14
                    anchors.verticalCenter: parent.verticalCenter
                    color: pill.on ? m3.inkSecondaryContainer : m3.inkMuted
                }
                Text {
                    id: caption
                    visible: !root.iconOnly
                    anchors.left: iconGlyph.right
                    anchors.leftMargin: 10
                    anchors.right: root.phone ? undefined : parent.right
                    anchors.rightMargin: root.phone ? 0 : 12
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: modelData.label
                    color: pill.on ? m3.inkSecondaryContainer : m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    font.weight: pill.on ? 600 : 500
                }
                HoverHandler { id: hover }
                TapHandler { id: tap; onTapped: root.picked(modelData.name) }
                Keys.onPressed: (event) => {
                    var key = event.key
                    var at = -1
                    for (var i = 0; i < root.sections.length; i++) {
                        if (root.sections[i].name === modelData.name)
                            at = i
                    }
                    if (key === Qt.Key_Space || key === Qt.Key_Return || key === Qt.Key_Enter) {
                        root.picked(modelData.name)
                        event.accepted = true
                    } else if (key === Qt.Key_Down || key === Qt.Key_Right || key === Qt.Key_Up || key === Qt.Key_Left) {
                        var forward = key === Qt.Key_Down || key === Qt.Key_Right
                        var next = Math.max(0, Math.min(root.sections.length - 1, at + (forward ? 1 : -1)))
                        root.picked(root.sections[next].name)
                        pills.itemAt(next).forceActiveFocus()
                        event.accepted = true
                    }
                }
            }
        }
    }
}
