import QtQuick
import QtQuick.Layouts
import components 1.0

Rectangle {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string heading: ""
    property var lines: null
    signal closeRequested()
    signal openRequested()

    objectName: "monthDateBar"
    radius: 16
    color: tones.surfaceContainer
    implicitHeight: Math.max(56, body.implicitHeight + 16)
    Accessible.role: Accessible.Grouping
    Accessible.name: heading
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape) {
            root.closeRequested()
            event.accepted = true
        }
    }

    M3Palette { id: tones; theme: root.theme }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 8
        anchors.topMargin: 8
        anchors.bottomMargin: 8
        spacing: 8

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 2

            Text {
                objectName: "monthDateHeading"
                Layout.fillWidth: true
                text: root.heading
                color: tones.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(14)
                font.weight: 500
                elide: Text.ElideRight
            }

            Repeater {
                model: root.lines

                Text {
                    objectName: "monthDateItem"
                    Layout.fillWidth: true
                    text: model.label
                    wrapMode: Text.WordWrap
                    color: tones.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(13)
                    font.weight: 500
                }
            }
        }

        Button {
            objectName: "monthClose"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Close"
            onClicked: root.closeRequested()
        }

        Button {
            objectName: "monthOpenDay"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Open Day"
            onClicked: root.openRequested()
        }
    }
}
