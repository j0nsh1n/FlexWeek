import QtQuick
import components 1.0

// A dialog with up to three buttons, an optional one-line field, and an optional read-only text area.
FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: false
    property string title: ""
    property string body: ""
    property string error: ""
    property bool showField: false
    property string fieldLabel: ""
    property string fieldText: ""
    property string shownText: ""
    property var buttons: []
    signal picked(string value, string text)
    signal dismissed()

    anchors.fill: parent
    visible: open
    focus: open
    z: 30

    M3Palette { id: palette; theme: root.theme }

    function copyShown() {
        shownArea.selectAll()
        shownArea.copy()
        shownArea.deselect()
    }

    function cycle(step) {
        FocusCycle.take(FocusCycle.nextItem([card], step, Window.activeFocusItem), step)
    }

    function focusFirst() {
        if (field.visible)
            field.forceActiveFocus()
        else
            root.forceActiveFocus()
    }

    Rectangle {
        anchors.fill: parent
        color: palette.scrim
        opacity: 0.32
        TapHandler { onTapped: root.dismissed() }
    }
    Rectangle {
        id: card
        objectName: "promptCard"
        width: Math.min(480, Math.max(0, root.width - 32))
        height: column.implicitHeight + 48
        radius: palette.cornerFor(24)
        anchors.centerIn: parent
        color: palette.dialogSurface
        border.width: root.highContrast ? 1.5 : (palette.dark ? 1 : 0)
        border.color: root.highContrast ? palette.outline : palette.outlineVariant
        Column {
            id: column
            x: 24
            y: 24
            width: card.width - 48
            spacing: 16
            Text {
                width: parent.width
                text: root.title
                color: palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: M3Font.px(24)
                wrapMode: Text.WordWrap
            }
            Text {
                visible: root.body !== ""
                width: parent.width
                text: root.body
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(14)
                wrapMode: Text.WordWrap
            }
            OutlinedField {
                id: field
                objectName: "promptField"
                visible: root.showField
                width: parent.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: root.fieldLabel
                text: root.fieldText
                accessName: root.fieldLabel
            }
            Rectangle {
                visible: root.shownText !== ""
                width: parent.width
                height: 160
                radius: 8
                color: palette.surfaceContainerLowest
                border.width: 1
                border.color: palette.outlineVariant
                clip: true
                Flickable {
                    anchors.fill: parent
                    anchors.margins: 8
                    contentWidth: width
                    contentHeight: shownArea.implicitHeight
                    clip: true
                    TextEdit {
                        id: shownArea
                        objectName: "promptShown"
                        width: parent.width
                        readOnly: true
                        selectByMouse: true
                        text: root.shownText
                        wrapMode: TextEdit.WrapAnywhere
                        color: palette.inkSurface
                        font.family: "monospace"
                        font.pixelSize: M3Font.px(12)
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Exported look"
                    }
                }
            }
            Text {
                objectName: "promptError"
                visible: root.error !== ""
                width: parent.width
                text: root.error
                color: palette.error
                font.family: M3Font.family
                font.pixelSize: M3Font.px(14)
                wrapMode: Text.WordWrap
            }
            Item {
                id: footer
                objectName: "promptFooter"
                width: parent.width
                height: actions.height
                // One row while the buttons fit; when they do not, one column, right-aligned, Cancel on
                // top and the main choice at the bottom.
                property bool stacked: false
                // Hidden until the first fit, so no frame shows buttons side by side that are about to stack.
                property bool fitted: false
                opacity: fitted ? 1 : 0
                function fit() {
                    var total = 0
                    var count = 0
                    for (var i = 0; i < actions.children.length; i++) {
                        var kid = actions.children[i]
                        var wide = kid.implicitWidth > 0 ? kid.implicitWidth : kid.width
                        if (!kid.visible || !(wide > 0))
                            continue
                        total += wide
                        count++
                    }
                    footer.stacked = count > 0 && total + 8 * (count - 1) > footer.width
                    footer.fitted = true
                }
                onWidthChanged: Qt.callLater(fit)
                Component.onCompleted: Qt.callLater(fit)
                Grid {
                    id: actions
                    x: footer.width - width
                    columns: footer.stacked ? 1 : 100
                    horizontalItemAlignment: Grid.AlignRight
                    spacing: 8
                    onChildrenChanged: Qt.callLater(footer.fit)
                    Repeater {
                        model: root.buttons
                        delegate: Button {
                            objectName: "prompt_" + modelData.value
                            theme: root.theme
                            density: root.density
                            reduceMotion: root.reduceMotion
                            highContrast: root.highContrast
                            kind: modelData.kind || "text"
                            text: modelData.label
                            accessName: modelData.label
                            onClicked: root.picked(modelData.value, field.text)
                        }
                    }
                }
            }
        }
    }
    Accessible.role: Accessible.Dialog
    Accessible.name: root.title
    onOpenChanged: if (open) Qt.callLater(root.focusFirst)
    Keys.onEscapePressed: (event) => {
        root.dismissed()
        event.accepted = true
    }
    Keys.priority: Keys.BeforeItem
    Keys.onTabPressed: (event) => {
        root.cycle(1)
        event.accepted = true
    }
    Keys.onBacktabPressed: (event) => {
        root.cycle(-1)
        event.accepted = true
    }
}
