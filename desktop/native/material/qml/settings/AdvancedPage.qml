import QtQuick
import components 1.0

// The full-page advanced settings: controls on the left, the live preview on the right, a foot bar below.
// Everything is a draft until Done.
Item {
    id: root
    objectName: "advancedPage"
    readonly property var st: Ui.st
    readonly property var panel: Ui.settings
    readonly property bool wide: !Ui.phone && width >= 900
    readonly property bool prompting: !!root.st.prompt

    M3Palette { id: palette; theme: Ui.theme }

    function importPick(value, text) {
        if (value === "import")
            panel.confirmPrompt(text)
        else
            panel.dismissPrompt()
    }

    Rectangle { anchors.fill: parent; color: palette.surface }

    Item {
        id: top
        enabled: !root.prompting
        width: parent.width
        height: 64
        IconButton {
            objectName: "advancedBack"
            x: 8
            anchors.verticalCenter: parent.verticalCenter
            theme: Ui.theme
            density: Ui.density
            reduceMotion: Ui.reduceMotion
            highContrast: Ui.highContrast
            icon: "arrow_back"
            accessName: "Back to settings"
            onClicked: root.panel.closeAdvanced()
        }
        Text {
            x: 64
            anchors.verticalCenter: parent.verticalCenter
            text: "Advanced settings"
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 22
            font.weight: 500
        }
    }

    Item {
        id: body
        enabled: !root.prompting
        anchors.top: top.bottom
        anchors.bottom: foot.top
        anchors.left: parent.left
        anchors.right: parent.right

        SectionPage {
            id: controls
            objectName: "advancedControls"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: root.wide ? Math.min(460, parent.width * 0.42) : parent.width
            maxWidth: 520

            Rectangle {
                objectName: "advancedBanner"
                width: parent.width
                height: banner.implicitHeight + 24
                radius: 16
                color: palette.primaryContainer
                Text {
                    id: banner
                    x: 16
                    y: 12
                    width: parent.width - 32
                    text: "Layered on the " + (root.st.draftPreset || "") + " preset, " + (root.st.draftMode || "")
                          + ". Basic settings stay in Look."
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.family
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }
            }
            Item {
                visible: !root.wide
                width: parent.width
                height: root.wide ? 0 : 340
                Loader {
                    anchors.fill: parent
                    active: !root.wide
                    sourceComponent: PreviewStage {}
                }
            }

            Group {
                GroupHeader { title: "Shape"; resetKey: "shape"; onReset: root.panel.resetGroup("shape") }
                SliderRow {
                    key: "corner"; title: "Corner radius"; unit: " px"
                    from: 0; to: 28; step: 1; value: root.st.corner === undefined ? 12 : root.st.corner
                    onMoved: (v) => root.panel.setCorner(v)
                }
            }
            Group {
                GroupHeader { title: "Density"; resetKey: "density"; onReset: root.panel.resetGroup("density") }
                SliderRow {
                    key: "hour"; title: "Hour row height"; unit: " px"
                    from: 36; to: 90; step: 2; value: root.st.hour === undefined ? 56 : root.st.hour
                    onMoved: (v) => root.panel.setHour(v)
                }
                SliderRow {
                    key: "padding"; title: "Card padding"; unit: " px"
                    from: 4; to: 24; step: 1; value: root.st.padding === undefined ? 6 : root.st.padding
                    onMoved: (v) => root.panel.setPadding(v)
                }
                ToggleRow {
                    key: "rail"; title: "Rail labels"; subtitle: "Words under the rail icons."
                    isOn: !!root.st.rail
                    onFlipped: (v) => root.panel.setRail(v)
                }
            }
            Group {
                GroupHeader { title: "Type"; resetKey: "type"; onReset: root.panel.resetGroup("type") }
                SliderRow {
                    key: "scale"; title: "Text scale"; unit: "×"; decimals: 2
                    from: 0.9; to: 1.8; step: 0.05; value: root.st.scale === undefined ? 1 : root.st.scale
                    onMoved: (v) => root.panel.setScale(v)
                }
            }
            Group {
                GroupHeader { title: "Motion"; resetKey: "motion"; onReset: root.panel.resetGroup("motion") }
                ChoiceRow {
                    key: "motionSpeed"; title: "Speed"; subtitle: "How fast things move."
                    choices: [{ label: "Slower", value: "Slower" }, { label: "Normal", value: "Normal" },
                              { label: "Faster", value: "Faster" }, { label: "Off", value: "Off" }]
                    current: root.st.draftMotion || "Normal"
                    onChosen: (v) => root.panel.setMotion(v)
                }
            }
            Group {
                GroupHeader { title: "Depth"; resetKey: "depth"; onReset: root.panel.resetGroup("depth") }
                SliderRow {
                    key: "shadow"; title: "Shadow strength"
                    from: 0; to: 3; step: 1; value: root.st.shadow === undefined ? 0 : root.st.shadow
                    onMoved: (v) => root.panel.setShadow(v)
                }
            }
            Group {
                GroupHeader { title: "Calendar"; resetKey: "calendar"; onReset: root.panel.resetGroup("calendar") }
                ChoiceRow {
                    key: "block"; title: "Block style"; subtitle: "How an event is drawn."
                    choices: [{ label: "Edge", value: "Edge" }, { label: "Filled", value: "Filled" }, { label: "Outline", value: "Outline" }]
                    current: root.st.block || "Edge"
                    onChosen: (v) => root.panel.setBlock(v)
                }
                ChoiceRow {
                    key: "lines"; title: "Hour lines"; subtitle: "The rules across the week."
                    choices: [{ label: "None", value: "None" }, { label: "Faint", value: "Faint" }, { label: "Clear", value: "Clear" }]
                    current: root.st.lines || "Faint"
                    onChosen: (v) => root.panel.setLines(v)
                }
                ToggleRow {
                    key: "today"; title: "Today highlight"; subtitle: "Bold today's column heading."
                    isOn: !!root.st.today
                    onFlipped: (v) => root.panel.setToday(v)
                }
                ToggleRow {
                    key: "times"; title: "Show times"; subtitle: "Start and end on each block."
                    isOn: !!root.st.times
                    onFlipped: (v) => root.panel.setTimes(v)
                }
                ToggleRow {
                    key: "lengths"; title: "Show lengths"; subtitle: "Minutes on each block."
                    isOn: !!root.st.lengths
                    onFlipped: (v) => root.panel.setLengths(v)
                }
                ColorRow {
                    key: "now"; title: "Now line"; value: root.st.now || ""; fallback: Ui.theme.primary || "#425e91"
                    onEdited: (v) => root.panel.setNow(v)
                }
                ColorRow {
                    key: "catSchool"; title: "School"; value: root.st.catSchool || ""
                    onEdited: (v) => root.panel.setCategory("school", v)
                }
                ColorRow {
                    key: "catSports"; title: "Soccer and sports"; value: root.st.catSports || ""
                    onEdited: (v) => root.panel.setCategory("sports", v)
                }
                ColorRow {
                    key: "catStudy"; title: "Study"; value: root.st.catStudy || ""
                    onEdited: (v) => root.panel.setCategory("study", v)
                }
                ColorRow {
                    key: "catHomework"; title: "Homework"; value: root.st.catHomework || ""
                    onEdited: (v) => root.panel.setCategory("homework", v)
                }
            }
            Group {
                objectName: "readability"
                GroupHeader { title: "Readability" }
                SettingsRow {
                    objectName: "row_readable"
                    visible: (root.st.problems || []).length === 0
                    title: "Everything you set reads clearly."
                    subtitle: "Colours you set are checked against their text."
                }
                Repeater {
                    model: root.st.problems || []
                    delegate: SettingsRow {
                        objectName: "problem_" + modelData.role
                        title: modelData.words
                        subtitle: "Contrast " + modelData.ratio + " to 1, needs " + (modelData.role === "now" ? "3" : "4.5") + "."
                        Button {
                            objectName: "fix_" + modelData.role
                            theme: Ui.theme
                            density: Ui.density
                            reduceMotion: Ui.reduceMotion
                            highContrast: Ui.highContrast
                            kind: "tonal"
                            text: "Fix"
                            accessName: "Fix " + modelData.words
                            onClicked: root.panel.fixRole(modelData.role)
                        }
                    }
                }
                SettingsRow {
                    objectName: "row_fixAll"
                    visible: (root.st.problems || []).length > 1
                    title: "Fix all"
                    subtitle: "Nudge every failing colour until it reads."
                    Button {
                        objectName: "fixAll"
                        theme: Ui.theme
                        density: Ui.density
                        reduceMotion: Ui.reduceMotion
                        highContrast: Ui.highContrast
                        kind: "filled"
                        text: "Fix all"
                        accessName: "Fix all colours"
                        onClicked: root.panel.fixAll()
                    }
                }
            }
        }

        Loader {
            active: root.wide
            visible: active
            anchors.left: controls.right
            anchors.leftMargin: 24
            anchors.right: parent.right
            anchors.rightMargin: 24
            anchors.top: parent.top
            anchors.topMargin: 12
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12
            sourceComponent: PreviewStage {}
        }
    }

    Rectangle {
        id: foot
        objectName: "advancedFoot"
        enabled: !root.prompting
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.wide ? 72 : 120
        color: palette.surfaceContainer
        Rectangle { width: parent.width; height: 1; color: palette.outlineVariant }
        Flow {
            x: 16
            y: root.wide ? (parent.height - height) / 2 : 12
            width: root.wide ? 460 : parent.width - 32
            spacing: 8
            Button {
                objectName: "resetAll"
                theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
                kind: "text"; text: "Reset all"; accessName: "Reset all"
                onClicked: root.panel.resetAdvanced()
            }
            Button {
                objectName: "importLook"
                theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
                kind: "outlined"; text: "Import"; accessName: "Import a look"
                onClicked: root.panel.beginImport()
            }
            Button {
                objectName: "exportLook"
                theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
                kind: "outlined"; text: "Export"; accessName: "Export this look"
                onClicked: root.panel.beginExport()
            }
            Button {
                objectName: "saveLook"
                theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
                kind: "tonal"; text: "Save as new"; accessName: "Save as a new look"
                onClicked: root.panel.beginSave()
            }
        }
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: root.wide ? parent.verticalCenter : undefined
            anchors.bottom: root.wide ? undefined : parent.bottom
            anchors.bottomMargin: 12
            spacing: 16
            Text {
                objectName: "draftState"
                visible: root.wide
                anchors.verticalCenter: parent.verticalCenter
                text: root.st.dirty ? "Draft. Done applies it." : "Same as the preset"
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: 12
            }
            Button {
                objectName: "advancedDone"
                theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
                kind: "filled"; text: "Done"; accessName: "Done"
                onClicked: root.panel.done()
            }
        }
    }

    Prompt {
        objectName: "importPrompt"
        theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
        open: root.st.prompt === "import"
        title: "Import a look"
        body: "Paste a look you exported from FlexWeek."
        showField: true
        fieldLabel: "Look text"
        error: root.st.importError || ""
        buttons: [{ label: "Cancel", value: "cancel", kind: "text" }, { label: "Import", value: "import", kind: "filled" }]
        onPicked: (value, text) => root.importPick(value, text)
        onDismissed: root.panel.dismissPrompt()
    }
    Prompt {
        objectName: "savePrompt"
        theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
        open: root.st.prompt === "save"
        title: "Save as a new look"
        body: "Keeps the values in the preview. It appears under Saved looks."
        showField: true
        fieldLabel: "Name"
        error: root.st.saveError || ""
        buttons: [{ label: "Cancel", value: "cancel", kind: "text" }, { label: "Save", value: "save", kind: "filled" }]
        onPicked: (value, text) => {
            if (value === "save")
                root.panel.confirmPrompt(text)
            else
                root.panel.dismissPrompt()
        }
        onDismissed: root.panel.dismissPrompt()
    }
    Prompt {
        id: exportPrompt
        objectName: "exportPrompt"
        theme: Ui.theme; density: Ui.density; reduceMotion: Ui.reduceMotion; highContrast: Ui.highContrast
        open: root.st.prompt === "export"
        title: "Export this look"
        body: "Copy this text to keep or share the look."
        shownText: root.st.exportText || ""
        buttons: [{ label: "Close", value: "close", kind: "text" }, { label: "Copy", value: "copy", kind: "filled" }]
        onPicked: (value, text) => {
            if (value === "copy")
                exportPrompt.copyShown()
            else
                root.panel.dismissPrompt()
        }
        onDismissed: root.panel.dismissPrompt()
    }
}
