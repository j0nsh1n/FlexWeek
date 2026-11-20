import QtQuick
import components 1.0

// Add alarm and Edit alarm, from Settings > Alerts: name, time, days, sound and an optional Spotify link.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "alarmSheet"
    initialFocus: nameField
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    SyncField {
        id: nameField
        objectName: "alarmName"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "Name"
        placeholder: "Alarm"
        wanted: root.f.name ? root.f.name : ""
        onTextEdited: (value) => root.sheets.setAlarmText("name", value)
        Keys.onReturnPressed: root.sheets.saveAlarm()
        Keys.onEnterPressed: root.sheets.saveAlarm()
    }
    Row {
        width: parent.width
        spacing: 12
        PickerField {
            objectName: "alarmHour"
            width: (parent.width - 12) / 2
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Hour"
            options: root.f.hours ? root.f.hours : []
            value: root.f.hour
            onPicked: (v) => root.sheets.setAlarmNumber("hour", v)
        }
        PickerField {
            objectName: "alarmMinute"
            width: (parent.width - 12) / 2
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Minute"
            options: root.f.minutes ? root.f.minutes : []
            value: root.f.minute
            onPicked: (v) => root.sheets.setAlarmNumber("minute", v)
        }
    }
    Column {
        width: parent.width
        spacing: 6
        Text { text: "Days"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: M3Font.px(12) }
        Flow {
            objectName: "alarmDays"
            width: parent.width
            spacing: 8
            Repeater {
                model: root.f.days ? root.f.days : []
                delegate: Item {
                    id: day
                    objectName: "alarmDay" + index
                    width: 60
                    height: 40
                    activeFocusOnTab: true
                    Accessible.role: Accessible.CheckBox
                    Accessible.name: modelData.full
                    Accessible.checkable: true
                    Accessible.checked: modelData.on
                    Accessible.onPressAction: root.sheets.toggleAlarmDay(index)
                    Rectangle {
                        anchors.fill: parent
                        radius: 12
                        color: modelData.on ? pal.secondaryContainer : "transparent"
                        border.width: modelData.on ? 0 : 1
                        border.color: pal.outline
                    }
                    // The check says "picked" without relying on the tint alone, as the chips in Settings do.
                    Row {
                        anchors.centerIn: parent
                        spacing: 4
                        M3Icon {
                            objectName: modelData.on ? "alarmDayCheck" : ""
                            visible: modelData.on
                            name: "check"
                            width: 16
                            height: 16
                            color: pal.inkSecondaryContainer
                        }
                        Text {
                            text: modelData.label
                            color: modelData.on ? pal.inkSecondaryContainer : pal.inkSurface
                            font.family: M3Font.family
                            font.pixelSize: M3Font.px(14)
                            font.weight: 500
                        }
                    }
                    M3StateLayer {
                        anchors.fill: parent
                        radius: 12
                        color: pal.inkSurface
                        hovered: dayHover.hovered
                        reduceMotion: root.reduceMotion
                    }
                    M3FocusRing { anchors.fill: parent; anchors.margins: -4; ring: pal.focusRing; ringRadius: 16 }
                    HoverHandler { id: dayHover }
                    TapHandler { onTapped: root.sheets.toggleAlarmDay(index) }
                    Keys.onPressed: (event) => {
                        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.sheets.toggleAlarmDay(index)
                            event.accepted = true
                        }
                    }
                }
            }
        }
        FieldNote { objectName: "alarmDaysProblem"; theme: root.theme; problem: true; text: root.f.daysProblem ? root.f.daysProblem : "" }
    }
    PickerField {
        objectName: "alarmSound"
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "Sound"
        options: root.f.sounds ? root.f.sounds : []
        value: root.f.sound
        onPicked: (v) => root.sheets.setAlarmText("sound", v)
    }
    Column {
        width: parent.width
        spacing: 4
        SyncField {
            objectName: "alarmLink"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Spotify link"
            placeholder: "Optional"
            wanted: root.f.link ? root.f.link : ""
            onTextEdited: (value) => root.sheets.setAlarmText("link", value)
            Keys.onReturnPressed: root.sheets.saveAlarm()
            Keys.onEnterPressed: root.sheets.saveAlarm()
        }
        FieldNote { objectName: "alarmLinkProblem"; theme: root.theme; problem: true; text: root.f.linkProblem ? root.f.linkProblem : "" }
    }
    Row {
        width: parent.width
        spacing: 16
        Text {
            width: parent.width - 52 - 16
            anchors.verticalCenter: parent.verticalCenter
            text: "Alarm is on"
            color: pal.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(16)
        }
        Switch {
            objectName: "alarmEnabled"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            accessName: "Alarm is on"
            checked: !!root.f.enabled
            onToggled: (on) => root.sheets.setAlarmEnabled(on)
        }
    }
    FieldNote { objectName: "alarmError"; theme: root.theme; problem: true; text: root.f.error ? root.f.error : "" }

    leading: [
        Button {
            objectName: "alarmDelete"
            visible: !!root.f.canRemove
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Delete"
            accessName: "Delete alarm"
            onClicked: root.sheets.removeAlarm()
        }
    ]
    trailing: [
        Button {
            objectName: "alarmCancel"
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
            objectName: "alarmSave"
            enabled: root.sheets && root.sheets.canSave
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: root.f.canRemove ? "Save" : "Add alarm"
            accessName: text
            onClicked: root.sheets.saveAlarm()
        }
    ]
}
