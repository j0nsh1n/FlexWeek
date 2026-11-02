import QtQuick
import components 1.0

// Add fixed time (What, When, Category) and Edit fixed time (one page).
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    readonly property int step: f.step === undefined ? 0 : f.step
    function shows(n) { return step < 0 || step === n }
    heading: f.heading ? f.heading : ""
    objectName: "blockSheet"
    initialFocus: titleField
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Row {
        visible: root.step >= 0
        width: parent.width
        spacing: 8
        Repeater {
            model: root.f.crumbs ? root.f.crumbs : []
            delegate: Item {
                id: crumb
                objectName: "blockCrumb" + index
                readonly property bool reachable: modelData.done
                width: crumbText.implicitWidth + 24
                height: 32
                activeFocusOnTab: reachable
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label + (modelData.summary ? ", " + modelData.summary : "")
                Accessible.onPressAction: if (reachable) root.sheets.goto(index)
                Rectangle {
                    anchors.fill: parent
                    radius: 8
                    color: modelData.on ? pal.secondaryContainer : "transparent"
                    border.width: modelData.on ? 0 : 1
                    border.color: pal.outline
                }
                Text {
                    id: crumbText
                    anchors.centerIn: parent
                    text: modelData.label
                    color: modelData.on ? pal.inkSecondaryContainer : pal.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: 500
                }
                M3FocusRing { anchors.fill: parent; anchors.margins: -3; shown: crumb.activeFocus; ring: pal.primary; ringRadius: 11 }
                TapHandler { enabled: crumb.reachable; onTapped: root.sheets.goto(index) }
                Keys.onPressed: (event) => {
                    if (crumb.reachable && (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                        root.sheets.goto(index)
                        event.accepted = true
                    }
                }
            }
        }
    }
    Text {
        objectName: "blockPrompt"
        visible: root.step >= 0
        width: parent.width
        text: root.f.prompt ? root.f.prompt : ""
        color: pal.inkSurface
        font.family: M3Font.family
        font.pixelSize: 14
    }

    // What
    Column {
        visible: root.shows(0)
        width: parent.width
        spacing: 4
        SyncField {
            id: titleField
            objectName: "blockTitle"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Title"
            wanted: root.f.title ? root.f.title : ""
            onTextEdited: (value) => root.sheets.setText("title", value)
            Keys.onReturnPressed: root.sheets.next()
            Keys.onEnterPressed: root.sheets.next()
        }
        FieldNote { objectName: "blockTitleProblem"; theme: root.theme; problem: true; text: root.f.titleProblem ? root.f.titleProblem : "" }
    }

    // When
    Column {
        visible: root.shows(1)
        width: parent.width
        spacing: 12
        Column {
            visible: !!root.f.showScope
            width: parent.width
            spacing: 6
            Text { text: "Apply to"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 12 }
            SegmentedButton {
                objectName: "editScope"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                accessName: "Apply to"
                choices: root.f.scopeChoices ? root.f.scopeChoices : []
                current: root.f.scope ? root.f.scope : "series"
                onSelected: (v) => root.sheets.setText("scope", v)
            }
        }
        Column {
            width: parent.width
            spacing: 6
            Text { text: "Days"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 12 }
            Flow {
                objectName: "blockDays"
                width: parent.width
                spacing: 8
                Repeater {
                    model: root.f.days ? root.f.days : []
                    delegate: Item {
                        id: day
                        objectName: "blockDay" + index
                        width: 52
                        height: 40
                        enabled: !root.f.daysLocked
                        activeFocusOnTab: true
                        Accessible.role: Accessible.CheckBox
                        Accessible.name: modelData.label + " " + modelData.date
                        Accessible.checkable: true
                        Accessible.checked: modelData.on
                        Accessible.onPressAction: root.sheets.toggleDay(index)
                        Rectangle {
                            anchors.fill: parent
                            radius: 12
                            color: modelData.on ? pal.secondaryContainer : "transparent"
                            border.width: modelData.on ? 0 : 1
                            border.color: day.enabled ? pal.outline : pal.disabledInk
                        }
                        Text {
                            anchors.centerIn: parent
                            horizontalAlignment: Text.AlignHCenter
                            text: modelData.label + "\n" + modelData.date
                            color: !day.enabled ? pal.disabledInk : (modelData.on ? pal.inkSecondaryContainer : pal.inkSurface)
                            font.family: M3Font.family
                            font.pixelSize: 11
                            font.weight: 500
                            lineHeight: 0.9
                        }
                        M3StateLayer {
                            anchors.fill: parent
                            radius: 12
                            color: pal.inkSurface
                            hovered: dayHover.hovered && day.enabled
                            reduceMotion: root.reduceMotion
                        }
                        M3FocusRing { anchors.fill: parent; anchors.margins: -3; shown: day.activeFocus; ring: pal.primary; ringRadius: 15 }
                        HoverHandler { id: dayHover }
                        TapHandler { enabled: day.enabled; onTapped: root.sheets.toggleDay(index) }
                        Keys.onPressed: (event) => {
                            if (day.enabled && (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                                root.sheets.toggleDay(index)
                                event.accepted = true
                            }
                        }
                    }
                }
            }
            FieldNote { theme: root.theme; text: root.f.repeatNote ? root.f.repeatNote : "" }
            FieldNote { objectName: "blockDaysProblem"; theme: root.theme; problem: true; text: root.f.daysProblem ? root.f.daysProblem : "" }
            FieldNote { theme: root.theme; text: root.f.seriesNote ? root.f.seriesNote : "" }
        }
        Row {
            width: parent.width
            spacing: 12
            PickerField {
                objectName: "blockStart"
                width: (parent.width - 12) / 2
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Start"
                options: root.f.startOptions ? root.f.startOptions : []
                value: root.f.start
                onPicked: (v) => root.sheets.setText("start", v)
            }
            PickerField {
                objectName: "blockEnd"
                width: (parent.width - 12) / 2
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "End"
                options: root.f.endOptions ? root.f.endOptions : []
                value: root.f.end
                onPicked: (v) => root.sheets.setNumber("end", v)
            }
        }
        Row {
            spacing: 8
            Text { text: "Duration"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
            Text {
                objectName: "blockDurationLine"
                text: root.f.durationLine ? root.f.durationLine : ""
                color: root.f.durationIsProblem ? pal.error : pal.inkSurface
                font.family: M3Font.family
                font.pixelSize: 14
                font.weight: 500
                anchors.verticalCenter: parent.verticalCenter
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }
        }
        FieldNote { objectName: "blockTimeProblem"; theme: root.theme; problem: true; text: root.f.timeProblem ? root.f.timeProblem : "" }
        FieldNote { objectName: "blockClash"; theme: root.theme; text: root.f.clash ? root.f.clash : "" }
    }

    // Category
    PickerField {
        objectName: "blockCategory"
        visible: root.shows(2)
        width: parent.width
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "Category"
        options: root.f.categoryOptions ? root.f.categoryOptions : []
        value: root.f.category
        onPicked: (v) => root.sheets.setText("category", v)
    }
    Row {
        visible: !!root.f.showMissed && root.step < 0
        width: parent.width
        spacing: 16
        Text {
            width: parent.width - 52 - 16
            anchors.verticalCenter: parent.verticalCenter
            text: root.f.missedLabel ? root.f.missedLabel : ""
            color: pal.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
            wrapMode: Text.WordWrap
        }
        Switch {
            objectName: "blockMissed"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            accessName: root.f.missedLabel ? root.f.missedLabel : "I missed it"
            checked: !!root.f.missed
            onToggled: (on) => root.sheets.setFlag("missed", on)
        }
    }
    FieldNote { objectName: "blockError"; theme: root.theme; problem: true; text: root.f.error ? root.f.error : "" }

    leading: [
        Button {
            objectName: "deleteBlock"
            visible: !!root.f.canDelete
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Delete"
            accessName: "Delete fixed time"
            onClicked: root.sheets.remove()
        },
        Button {
            objectName: "blockBack"
            visible: !!root.f.canBack
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Back"
            accessName: "Back"
            onClicked: root.sheets.back()
        }
    ]
    trailing: [
        Button {
            objectName: "blockCancel"
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
            objectName: "blockNext"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: root.f.primary ? root.f.primary : "Next"
            accessName: text
            onClicked: root.sheets.next()
        }
    ]
}
