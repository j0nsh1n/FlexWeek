import QtQuick
import components 1.0

SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "routinesSheet"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        width: parent.width
        text: root.f.intro ? root.f.intro : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
    Text {
        objectName: "routinesEmpty"
        visible: text !== ""
        width: parent.width
        text: root.f.empty ? root.f.empty : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: 16
    }
    Repeater {
        model: root.f.rows ? root.f.rows : []
        delegate: ListRow {
            objectName: "routineRow"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: modelData.on ? "check" : ""
            title: modelData.name
            subtitle: modelData.detail
            accessName: modelData.name + ", " + modelData.detail + (modelData.on ? ", chosen" : "")
            onClicked: root.sheets.selectRoutine(modelData.id)
        }
    }
    Column {
        visible: !!root.f.selected
        width: parent.width
        spacing: 6
        Text { text: "Copy to"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 12 }
        Flow {
            width: parent.width
            spacing: 8
            Repeater {
                model: root.f.days ? root.f.days : []
                delegate: Item {
                    id: day
                    objectName: "routineDay" + index
                    width: 52
                    height: 40
                    activeFocusOnTab: true
                    Accessible.role: Accessible.CheckBox
                    Accessible.name: modelData.label + " " + modelData.date
                    Accessible.checkable: true
                    Accessible.checked: modelData.on
                    Accessible.onPressAction: root.sheets.toggleRoutineDay(index)
                    Rectangle {
                        anchors.fill: parent
                        radius: 12
                        color: modelData.on ? pal.secondaryContainer : "transparent"
                        border.width: modelData.on ? 0 : 1
                        border.color: pal.outline
                    }
                    Text {
                        anchors.centerIn: parent
                        horizontalAlignment: Text.AlignHCenter
                        text: modelData.label + "\n" + modelData.date
                        color: modelData.on ? pal.inkSecondaryContainer : pal.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: 11
                        font.weight: 500
                        lineHeight: 0.9
                    }
                    M3FocusRing { anchors.fill: parent; anchors.margins: -3; shown: day.activeFocus; ring: pal.primary; ringRadius: 15 }
                    TapHandler { onTapped: root.sheets.toggleRoutineDay(index) }
                    Keys.onPressed: (event) => {
                        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.sheets.toggleRoutineDay(index)
                            event.accepted = true
                        }
                    }
                }
            }
        }
    }
    FieldNote { objectName: "routinesError"; theme: root.theme; problem: true; text: root.f.error ? root.f.error : "" }
    trailing: [
        Button {
            objectName: "routinesCancel"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Cancel"
            accessName: "Cancel"
            onClicked: root.sheets.closeSheet()
        },
        Button {
            objectName: "routinesApply"
            enabled: !!root.f.selected
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: "Add to this week"
            accessName: "Add to this week"
            onClicked: root.sheets.applyRoutine()
        }
    ]
}
