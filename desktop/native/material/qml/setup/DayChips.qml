import QtQuick
import components 1.0

// Seven day buttons that each switch on and off. `days` holds the picked day numbers, Monday 0.
Flow {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property var names: []
    property var days: []
    property string prefix: "day"
    property string accessPrefix: ""
    signal toggled(int day)
    spacing: 8

    M3Palette { id: palette; theme: root.theme }

    Repeater {
        model: root.names
        Item {
            id: chip
            required property var modelData
            required property int index
            readonly property bool on: root.days.indexOf(index) >= 0
            width: 56
            height: 36
            objectName: root.prefix + index
            activeFocusOnTab: true
            property bool keyDown: false
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: chip.on ? palette.secondaryContainer : "transparent"
                border.width: chip.on ? 0 : (root.highContrast ? 1.5 : 1)
                border.color: palette.outline
            }
            M3StateLayer {
                anchors.fill: parent
                radius: 8
                color: chip.on ? palette.inkSecondaryContainer : palette.inkSurface
                hovered: hover.hovered
                down: tap.pressed || chip.keyDown
                reduceMotion: root.reduceMotion
            }
            M3FocusRing {
                anchors.fill: parent
                anchors.margins: -3
                shown: chip.activeFocus
                ring: palette.primary
                ringRadius: 11
            }
            Row {
                anchors.centerIn: parent
                spacing: 4
                M3Icon {
                    visible: chip.on
                    name: "check"
                    width: 16
                    height: 16
                    color: palette.inkSecondaryContainer
                }
                Text {
                    text: chip.modelData.short
                    color: chip.on ? palette.inkSecondaryContainer : palette.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: 500
                }
            }
            HoverHandler { id: hover }
            TapHandler { id: tap; onTapped: root.toggled(chip.index) }
            Accessible.role: Accessible.CheckBox
            Accessible.name: root.accessPrefix + chip.modelData.full
            Accessible.checkable: true
            Accessible.checked: chip.on
            Accessible.onPressAction: root.toggled(chip.index)
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    chip.keyDown = true
                    event.accepted = true
                }
            }
            Keys.onReleased: (event) => {
                if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    if (chip.keyDown)
                        root.toggled(chip.index)
                    chip.keyDown = false
                    event.accepted = true
                }
            }
        }
    }
}
