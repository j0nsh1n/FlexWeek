import QtQuick
import components 1.0

// Add homework (What, When, How long) and Edit homework (one page).
SheetFrame {
    id: root
    property var sheets
    readonly property var f: sheets ? sheets.form : ({})
    readonly property int step: f.step === undefined ? 0 : f.step
    function shows(n) { return step < 0 || step === n }
    heading: f.heading ? f.heading : ""
    objectName: "homeworkSheet"
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
                objectName: "homeworkCrumb" + index
                readonly property bool reachable: modelData.done
                width: crumbText.implicitWidth + 24
                height: 32
                activeFocusOnTab: reachable
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label + (modelData.summary ? ", " + modelData.summary : "")
                Accessible.onPressAction: if (reachable) root.sheets.goto(index)
                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: modelData.on ? pal.secondaryContainer : "transparent"
                    border.width: 0
                    border.color: pal.outline
                }
                Text {
                    id: crumbText
                    anchors.centerIn: parent
                    text: modelData.label
                    color: modelData.on ? pal.inkSecondaryContainer : pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 14
                    font.weight: 500
                }
                M3FocusRing { anchors.fill: parent; anchors.margins: -4; ring: pal.focusRing; ringRadius: height / 2 + 4 }
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
        objectName: "homeworkPrompt"
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
            objectName: "homeworkTitle"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Title"
            placeholder: "e.g. History essay"
            wanted: root.f.title ? root.f.title : ""
            onTextEdited: (value) => root.sheets.setText("title", value)
            Keys.onReturnPressed: root.sheets.next()
            Keys.onEnterPressed: root.sheets.next()
        }
        FieldNote { objectName: "homeworkTitleProblem"; theme: root.theme; problem: true; text: root.f.titleProblem ? root.f.titleProblem : "" }
        FieldNote { theme: root.theme; text: root.f.placedLine ? root.f.placedLine : "" }
    }

    // When
    Column {
        visible: root.shows(1)
        width: parent.width
        spacing: 12
        Row {
            width: parent.width
            spacing: 12
            PickerField {
                id: dueField
                objectName: "homeworkDue"
                width: root.phone ? parent.width : (parent.width - 12) * 0.6
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Due"
                options: root.f.dueOptions ? root.f.dueOptions : []
                value: root.f.dueDate
                onPicked: (v) => root.sheets.setText("dueDate", v)
            }
            PickerField {
                objectName: "homeworkDueTime"
                visible: !root.phone
                width: (parent.width - 12) * 0.4
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Time"
                options: root.f.timeOptions ? root.f.timeOptions : []
                value: root.f.dueTime
                onPicked: (v) => root.sheets.setText("dueTime", v)
            }
        }
        PickerField {
            objectName: "homeworkDueTimePhone"
            visible: root.phone
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Time"
            options: root.f.timeOptions ? root.f.timeOptions : []
            value: root.f.dueTime
            onPicked: (v) => root.sheets.setText("dueTime", v)
        }
        FieldNote { objectName: "homeworkDueProblem"; theme: root.theme; problem: true; text: root.f.dueProblem ? root.f.dueProblem : "" }
        Column {
            visible: !!root.f.whenShown
            width: parent.width
            spacing: 12
            Text {
                text: "When"
                color: pal.inkMuted
                font.family: M3Font.family
                font.pixelSize: 12
            }
            SegmentedButton {
                objectName: "homeworkWhen"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                accessName: "When"
                choices: root.f.whenChoices ? root.f.whenChoices : []
                current: root.f.when ? root.f.when : "plan"
                onSelected: (v) => root.sheets.setText("when", v)
            }
            Row {
                visible: root.f.when === "fixed"
                width: parent.width
                spacing: 12
                PickerField {
                    objectName: "homeworkWhenDay"
                    width: (parent.width - 12) / 2
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    label: "Day"
                    options: root.f.dayOptions ? root.f.dayOptions : []
                    value: root.f.whenDay
                    onPicked: (v) => root.sheets.setNumber("whenDay", v)
                }
                PickerField {
                    objectName: "homeworkWhenTime"
                    width: (parent.width - 12) / 2
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    label: "Pinned time"
                    options: root.f.pinnedTimeOptions ? root.f.pinnedTimeOptions : []
                    value: root.f.whenTime
                    onPicked: (v) => root.sheets.setText("whenTime", v)
                }
            }
            FieldNote { theme: root.theme; text: root.f.whenNote ? root.f.whenNote : "" }
            FieldNote { theme: root.theme; text: root.f.whenFrom ? root.f.whenFrom : "" }
            FieldNote { objectName: "homeworkWhenProblem"; theme: root.theme; problem: true; text: root.f.whenProblem ? root.f.whenProblem : "" }
        }
    }

    // How long
    Column {
        visible: root.shows(2)
        width: parent.width
        spacing: 12
        SyncField {
            id: estimateField
            objectName: "homeworkEstimate"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Estimated time"
            accessName: "Estimated time"
            wanted: root.f.estimate ? root.f.estimate : ""
            onTextEdited: (value) => root.sheets.setText("estimate", value)
        }
        FieldNote {
            theme: root.theme
            text: root.f.estimateLabel ? root.f.estimateLabel : ""
        }
        SegmentedButton {
            objectName: "homeworkQuick"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            accessName: "Quick lengths"
            choices: root.f.quickLengths ? root.f.quickLengths : []
            current: root.f.estimate ? root.f.estimate : ""
            onSelected: (v) => root.sheets.setText("estimate", v)
        }
        FieldNote { objectName: "homeworkEstimateProblem"; theme: root.theme; problem: true; text: root.f.estimateProblem ? root.f.estimateProblem : "" }
        Column {
            visible: !!root.f.spreadShown
            width: parent.width
            spacing: 8
            Text {
                text: "Sessions"
                color: pal.inkMuted
                font.family: M3Font.family
                font.pixelSize: 12
            }
            SegmentedButton {
                objectName: "homeworkSpread"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                accessName: "Sessions"
                choices: root.f.spreadChoices ? root.f.spreadChoices : []
                current: root.f.spread ? root.f.spread : "one"
                onSelected: (v) => root.sheets.setText("spread", v)
            }
            FieldNote { objectName: "homeworkSpreadLine"; theme: root.theme; text: root.f.spreadLine ? root.f.spreadLine : "" }
        }
    }

    Row {
        visible: !!root.f.showFinished && root.shows(2)
        width: parent.width
        spacing: 16
        Text {
            width: parent.width - 52 - 16
            anchors.verticalCenter: parent.verticalCenter
            text: "Finished"
            color: pal.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
        }
        Switch {
            objectName: "homeworkCompleted"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            accessName: "Finished"
            checked: !!root.f.completed
            onToggled: (on) => root.sheets.setFlag("completed", on)
        }
    }

    Row {
        visible: !!root.f.canUnpin && root.shows(2)
        Button {
            objectName: "homeworkUnpin"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Unpin"
            accessName: "Unpin"
            onClicked: root.sheets.unpin()
        }
    }

    Button {
        objectName: "homeworkMoreDetails"
        visible: !!root.f.showDetails
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: root.f.detailsOpen ? "Fewer details" : "More details"
        accessName: text
        onClicked: root.sheets.setFlag("detailsOpen", !root.f.detailsOpen)
    }

    // More details
    Column {
        objectName: "homeworkDetails"
        visible: !!root.f.showDetails && !!root.f.detailsOpen
        width: parent.width
        spacing: 12
        SyncField {
            objectName: "homeworkCourse"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Course"
            wanted: root.f.course ? root.f.course : ""
            onTextEdited: (value) => root.sheets.setText("course", value)
        }
        PickerField {
            objectName: "homeworkPriority"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Type"
            options: root.f.typeOptions ? root.f.typeOptions : []
            value: root.f.priority
            onPicked: (v) => root.sheets.setNumber("priority", v)
        }
        FieldNote { theme: root.theme; text: "Tests are planned first, then quizzes, then everyday homework, then reading." }
        PickerField {
            objectName: "homeworkEnergy"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Energy preference"
            options: root.f.energyOptions ? root.f.energyOptions : []
            value: root.f.energy
            onPicked: (v) => root.sheets.setText("energy", v)
        }
        Item {
            width: parent.width
            height: 112
            Rectangle {
                id: notesShape
                anchors.fill: parent
                anchors.topMargin: 8
                radius: 6
                color: "transparent"
                border.width: root.highContrast ? 1.5 : 1
                border.color: pal.outline
            }
            M3FocusRing {
                anchors.fill: notesShape
                anchors.margins: -4
                target: notes
                ring: pal.focusRing
                ringRadius: 10
            }
            Rectangle {
                x: 12
                width: notesLabel.implicitWidth + 8
                height: 16
                color: pal.surfaceContainerHigh
                Text {
                    id: notesLabel
                    anchors.centerIn: parent
                    text: "Notes"
                    color: notes.activeFocus ? pal.primary : pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 12
                }
            }
            TextEdit {
                id: notes
                objectName: "homeworkNotes"
                anchors.fill: parent
                anchors.margins: 16
                anchors.topMargin: 20
                text: root.f.notes ? root.f.notes : ""
                color: pal.inkSurface
                font.family: M3Font.family
                font.pixelSize: 16
                wrapMode: TextEdit.Wrap
                clip: true
                selectByMouse: true
                activeFocusOnTab: true
                onTextChanged: if (text !== (root.f.notes ? root.f.notes : "")) root.sheets.setText("notes", text)
                Accessible.role: Accessible.EditableText
                Accessible.name: "Notes"
            }
        }
        Row {
            width: parent.width
            spacing: 8
            SyncField {
                id: linkLabel
                objectName: "homeworkLinkLabel"
                width: (parent.width - 8) * 0.35
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Link text"
                wanted: root.f.linkLabel ? root.f.linkLabel : ""
                onTextEdited: (value) => root.sheets.setText("linkLabel", value)
            }
            SyncField {
                objectName: "homeworkLinkUrl"
                width: (parent.width - 8) * 0.65
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Link address"
                placeholder: "https://"
                wanted: root.f.linkUrl ? root.f.linkUrl : ""
                onTextEdited: (value) => root.sheets.setText("linkUrl", value)
            }
        }
        Button {
            objectName: "addHomeworkLink"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Add link"
            accessName: "Add link"
            onClicked: root.sheets.addLink()
        }
        Repeater {
            model: root.f.links ? root.f.links : []
            delegate: Row {
                width: parent.width
                spacing: 8
                ListRow {
                    objectName: "homeworkLink"
                    width: parent.width - 48 - 8
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    title: modelData.label
                    subtitle: modelData.url
                }
                IconButton {
                    objectName: "removeHomeworkLink"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "close"
                    accessName: "Remove link " + modelData.label
                    onClicked: root.sheets.removeLink(index)
                }
            }
        }
        FieldNote { theme: root.theme; text: (root.f.links && root.f.links.length === 0) ? "No links yet" : "" }
        SyncField {
            objectName: "homeworkCheckText"
            width: parent.width
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Checklist step"
            accessName: "Step text"
            wanted: root.f.checkText ? root.f.checkText : ""
            onTextEdited: (value) => root.sheets.setText("checkText", value)
        }
        Button {
            objectName: "addHomeworkCheck"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "tonal"
            text: "Add step"
            accessName: "Add step"
            onClicked: root.sheets.addCheck()
        }
        Repeater {
            model: root.f.checklist ? root.f.checklist : []
            delegate: Row {
                width: parent.width
                spacing: 8
                ListRow {
                    objectName: "homeworkStep"
                    width: parent.width - 48 - 8
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: modelData.done ? "check" : ""
                    title: modelData.text
                    accessName: modelData.text + (modelData.done ? ", done" : ", not done")
                    onClicked: root.sheets.toggleCheck(index)
                }
                IconButton {
                    objectName: "removeHomeworkStep"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "close"
                    accessName: "Remove step " + modelData.text
                    onClicked: root.sheets.removeCheck(index)
                }
            }
        }
        FieldNote { theme: root.theme; text: (root.f.checklist && root.f.checklist.length === 0) ? "No steps yet" : "" }
        FieldNote { objectName: "homeworkDetailsError"; theme: root.theme; problem: true; text: root.f.detailsError ? root.f.detailsError : "" }
    }
    FieldNote { objectName: "homeworkError"; theme: root.theme; problem: true; text: root.f.error ? root.f.error : "" }

    leading: [
        Button {
            objectName: "deleteHomework"
            visible: !!root.f.canDelete
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "text"
            text: "Delete"
            accessName: "Delete homework"
            onClicked: root.sheets.remove()
        },
        Button {
            objectName: "homeworkBack"
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
            objectName: "homeworkCancel"
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
            objectName: "homeworkNext"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            kind: "filled"
            text: root.f.primary ? root.f.primary : "Next"
            accessName: text
            enabled: root.f.primary === "Next" || (root.sheets && root.sheets.canSave)
            onClicked: root.sheets.next()
        }
    ]
}
