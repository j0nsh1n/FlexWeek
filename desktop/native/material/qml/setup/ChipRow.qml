import QtQuick
import components 1.0

// A wrapped row of buttons, one picked: for choices too many or too long for a segmented button.
Flow {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property var choices: []
    property var current: ""
    property string prefix: "chip"
    property string accessPrefix: ""
    signal picked(var value)
    spacing: 8

    M3Palette { id: m3Palette; theme: root.theme }

    Repeater {
        model: root.choices.length
        Item {
            id: chip
            required property int index
            readonly property var modelData: root.choices[index] || ({value: "", label: ""})
            readonly property bool on: modelData.value === root.current
            width: caption.implicitWidth + (on ? 24 : 0) + 32
            height: 36
            objectName: root.prefix + "-" + modelData.value
            activeFocusOnTab: true
            property bool keyDown: false
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: chip.on ? m3Palette.secondaryContainer : "transparent"
                border.width: chip.on ? 0 : (root.highContrast ? 1.5 : 1)
                border.color: m3Palette.outline
            }
            M3StateLayer {
                anchors.fill: parent
                radius: 8
                color: chip.on ? m3Palette.inkSecondaryContainer : m3Palette.inkSurface
                hovered: hover.hovered
                down: tap.pressed || chip.keyDown
                reduceMotion: root.reduceMotion
            }
            M3FocusRing {
                anchors.fill: parent
                anchors.margins: -3
                shown: chip.activeFocus
                ring: m3Palette.primary
                ringRadius: 11
            }
            Row {
                anchors.centerIn: parent
                spacing: 6
                M3Icon {
                    visible: chip.on
                    name: "check"
                    width: 18
                    height: 18
                    color: m3Palette.inkSecondaryContainer
                }
                Text {
                    id: caption
                    text: chip.modelData.label
                    color: chip.on ? m3Palette.inkSecondaryContainer : m3Palette.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: 500
                }
            }
            HoverHandler { id: hover }
            TapHandler { id: tap; onTapped: root.picked(chip.modelData.value) }
            Accessible.role: Accessible.RadioButton
            Accessible.name: root.accessPrefix + chip.modelData.label
            Accessible.checkable: true
            Accessible.checked: chip.on
            Accessible.onPressAction: root.picked(chip.modelData.value)
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    chip.keyDown = true
                    event.accepted = true
                }
            }
            Keys.onReleased: (event) => {
                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    if (chip.keyDown)
                        root.picked(chip.modelData.value)
                    chip.keyDown = false
                    event.accepted = true
                }
            }
        }
    }
}
