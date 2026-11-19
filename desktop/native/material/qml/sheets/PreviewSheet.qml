import QtQuick
import components 1.0

// What a paste or a copy proposes, row by row: untick what you do not want, move a fixed time, save.
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    heading: f.heading ? f.heading : ""
    objectName: "previewSheet"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    Text {
        visible: text !== ""
        width: parent.width
        text: root.f.intro ? root.f.intro : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: root.f.rows ? root.f.rows : []
        delegate: Rectangle {
            id: card
            objectName: "previewRow"
            width: parent.width
            height: inner.implicitHeight + 24
            radius: 12
            color: pal.surfaceContainerLow
            // The same edge as a choice card: the sheet and the row share a fill in some looks.
            border.width: 1
            border.color: pal.outlineVariant
            Column {
                id: inner
                x: 12
                y: 12
                width: parent.width - 24
                spacing: 8
                Item {
                    id: head
                    width: parent.width
                    height: Math.max(M3Font.px(22), titleText.implicitHeight)
                    Rectangle {
                        id: box
                        objectName: "previewInclude" + modelData.index
                        width: M3Font.px(22)
                        height: width
                        radius: 4
                        anchors.verticalCenter: parent.verticalCenter
                        color: modelData.checked ? pal.primary : "transparent"
                        border.width: modelData.checked ? 0 : 2
                        border.color: pal.outline
                        opacity: modelData.invalid ? 0.38 : 1
                        activeFocusOnTab: !modelData.invalid
                        Accessible.role: Accessible.CheckBox
                        Accessible.name: modelData.title
                        Accessible.checkable: true
                        Accessible.checked: modelData.checked
                        Accessible.onToggleAction: if (!modelData.invalid) root.sheets.previewCheck(modelData.index, !modelData.checked)
                        Keys.onSpacePressed: if (!modelData.invalid) root.sheets.previewCheck(modelData.index, !modelData.checked)
                        M3Icon {
                            visible: modelData.checked
                            anchors.centerIn: parent
                            width: parent.width - 6
                            height: width
                            name: "check"
                            color: pal.inkPrimary
                        }
                        M3FocusRing {
                            anchors.fill: parent
                            anchors.margins: -4
                            target: box
                            ring: pal.focusRing
                            ringRadius: 8
                        }
                        TapHandler {
                            enabled: !modelData.invalid
                            onTapped: root.sheets.previewCheck(modelData.index, !modelData.checked)
                        }
                    }
                    Text {
                        id: titleText
                        anchors.left: box.right
                        anchors.leftMargin: 12
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.title
                        color: pal.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(16)
                        font.weight: 500
                        elide: Text.ElideRight
                    }
                }
                Row {
                    visible: modelData.fixed
                    width: parent.width
                    spacing: 8
                    PickerField {
                        objectName: "previewDay" + modelData.index
                        width: (parent.width - 16) / 3
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        label: "Day"
                        options: modelData.dayOptions ? modelData.dayOptions : []
                        value: modelData.day
                        onPicked: (v) => root.sheets.previewDay(modelData.index, v)
                    }
                    PickerField {
                        objectName: "previewStart" + modelData.index
                        width: (parent.width - 16) / 3
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        label: "Start"
                        options: modelData.startOptions ? modelData.startOptions : []
                        value: modelData.start
                        onPicked: (v) => root.sheets.previewStart(modelData.index, v)
                    }
                    PickerField {
                        objectName: "previewDuration" + modelData.index
                        width: (parent.width - 16) / 3
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        label: "Minutes"
                        options: modelData.durationOptions ? modelData.durationOptions : []
                        value: modelData.duration
                        onPicked: (v) => root.sheets.previewLength(modelData.index, v)
                    }
                }
                Text {
                    objectName: "previewDetail" + modelData.index
                    visible: text !== ""
                    width: parent.width
                    text: modelData.detail
                    color: modelData.invalid ? pal.error : pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(12)
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.StaticText
                    Accessible.name: modelData.title + ", " + text
                }
            }
        }
    }
    Text {
        objectName: "previewWhyOff"
        visible: text !== ""
        width: parent.width
        text: root.f.whyOff ? root.f.whyOff : ""
        color: pal.error
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        wrapMode: Text.WordWrap
    }
    trailing: [
        Button {
            objectName: "previewCancel"
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
            objectName: "previewSave"
            enabled: !!root.f.canSave
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: root.f.confirm ? root.f.confirm : "Save preview"
            accessName: text
            onClicked: root.sheets.savePreview()
        }
    ]
}
