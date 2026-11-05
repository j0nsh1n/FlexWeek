import QtQuick
import components 1.0

// The five section pills: a 220 wide column on a desktop, a scrolling strip on a phone.
Item {
    id: root
    property string current: "look"
    property bool phone: false
    signal picked(string name)
    readonly property var sections: [
        { name: "look", label: "Look" },
        { name: "planning", label: "Planning" },
        { name: "focus", label: "Focus" },
        { name: "alerts", label: "Alerts" },
        { name: "computer", label: "This computer" }
    ]

    M3Palette { id: m3; theme: Ui.theme }

    readonly property real wanted: pillFlow.height + 16

    Flow {
        id: pillFlow
        x: 12
        y: root.phone ? 8 : 12
        width: Math.max(0, root.width - 24)
        spacing: root.phone ? 8 : 4
        Repeater {
            id: pills
            model: root.sections
            delegate: Item {
                id: pill
                objectName: "section_" + modelData.name
                readonly property bool on: root.current === modelData.name
                width: root.phone ? caption.implicitWidth + 32 : root.width - 24
                height: root.phone ? 40 : 48
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.label
                Accessible.checkable: true
                Accessible.checked: on
                Accessible.onPressAction: root.picked(modelData.name)
                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: pill.on ? m3.secondaryContainer : "transparent"
                }
                M3StateLayer {
                    anchors.fill: parent
                    radius: height / 2
                    color: m3.inkSurface
                    hovered: hover.hovered && !pill.on
                    down: tap.pressed
                    reduceMotion: Ui.reduceMotion
                }
                M3FocusRing {
                    anchors.fill: parent
                    anchors.margins: -4
                    ring: m3.focusRing
                    ringRadius: parent.height / 2 + 4
                }
                Text {
                    id: caption
                    x: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    color: pill.on ? m3.inkSecondaryContainer : m3.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: 500
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
