import QtQuick
import QtQuick.Controls
import components 1.0

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool canZoomIn: true
    property bool canZoomOut: true
    signal zoomOut()
    signal zoomIn()

    width: pill.width
    height: 24

    M3Palette { id: palette; theme: root.theme }
    readonly property color inkMuted: palette.inkMuted
    readonly property color inkSurface: palette.inkSurface
    readonly property color focusRing: palette.focusRing
    readonly property color disabledInk: palette.disabledInk

    Rectangle {
        id: pill
        objectName: "weekZoom"
        width: outBtn.width + 1 + inBtn.width + 2
        height: 24
        radius: 12
        color: palette.surfaceContainer
        border.width: root.highContrast ? 1.5 : 1
        border.color: palette.outlineVariant

        Row {
            anchors.centerIn: parent
            spacing: 0

            ZoomBtn {
                id: outBtn
                objectName: "weekZoomOut"
                glyph: "−"
                accessName: "Zoom out"
                tip: "Zoom out (Ctrl+-)"
                enabled: root.canZoomOut
                onClicked: root.zoomOut()
            }
            Rectangle {
                width: 1
                height: 12
                anchors.verticalCenter: parent.verticalCenter
                color: palette.outlineVariant
            }
            ZoomBtn {
                id: inBtn
                objectName: "weekZoomIn"
                glyph: "+"
                accessName: "Zoom in"
                tip: "Zoom in (Ctrl+=)"
                enabled: root.canZoomIn
                onClicked: root.zoomIn()
            }
        }
    }

    component ZoomBtn: Item {
        id: btn
        property string glyph: "+"
        property string accessName: ""
        property string tip: ""
        signal clicked()

        width: 22
        height: 22
        property bool keyDown: false

        Rectangle {
            objectName: "shape"
            anchors.fill: parent
            radius: width / 2
            color: "transparent"
        }
        M3StateLayer {
            anchors.fill: parent
            radius: width / 2
            color: root.inkSurface
            hovered: hover.hovered && btn.enabled
            down: (tap.pressed || btn.keyDown) && btn.enabled
            reduceMotion: root.reduceMotion
        }
        M3FocusRing {
            anchors.fill: parent
            anchors.margins: -3
            ring: root.focusRing
            ringRadius: btn.width / 2 + 3
        }
        Text {
            anchors.centerIn: parent
            text: btn.glyph
            color: btn.enabled ? root.inkMuted : root.disabledInk
            font.family: M3Font.family
            font.pixelSize: 14
            font.weight: 500
        }

        HoverHandler { id: hover; enabled: btn.enabled }
        TapHandler { id: tap; enabled: btn.enabled; onTapped: btn.clicked() }
        ToolTip.visible: hover.hovered
        ToolTip.text: btn.tip
        ToolTip.delay: 400
        activeFocusOnTab: btn.enabled
        Accessible.role: Accessible.Button
        Accessible.name: btn.accessName
        Accessible.onPressAction: if (btn.enabled) btn.clicked()
        Keys.onPressed: (event) => {
            if (!btn.enabled)
                return
            if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                btn.keyDown = true
                event.accepted = true
            }
        }
        Keys.onReleased: (event) => {
            if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                var fire = btn.keyDown && btn.enabled
                btn.keyDown = false
                event.accepted = true
                if (fire)
                    Qt.callLater(function() { btn.clicked() })
            }
        }
    }
}
