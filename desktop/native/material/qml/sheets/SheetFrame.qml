import QtQuick
import components 1.0

// The frame every sheet shares: a dialog in the middle on a desktop, a bottom sheet under 768.
// Esc and a tap on the scrim ask to close. Tab stays inside the sheet.
FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    property string heading: ""
    property string accessName: ""
    property Item initialFocus: null
    default property alias content: body.data
    property alias leading: leadingRow.data
    property alias trailing: trailingRow.data
    signal closeRequested()

    anchors.fill: parent
    readonly property int margin: 24
    readonly property real cardWidth: phone ? width : Math.min(560, Math.max(0, width - 32))
    readonly property real chrome: (phone ? 12 + 4 + 16 : 24) + titleText.height + 16 + 16 + footer.height + 24

    M3Palette { id: pal; theme: root.theme }

    function cycle(step) {
        FocusCycle.take(FocusCycle.nextItem([body, footer], step, Window.activeFocusItem), step)
    }

    function focusTarget(item) {
        if (!item)
            return null
        var kids = item.children ? item.children : []
        for (var i = 0; i < kids.length; i++) {
            if (kids[i].objectName === "fieldInput" && kids[i].visible && kids[i].enabled)
                return kids[i]
        }
        return item
    }

    function focusFirst() {
        var start = focusTarget(initialFocus)
        if (start && start.visible && start.enabled) {
            start.forceActiveFocus()
            return
        }
        var all = FocusCycle.focusables(body, [])
        if (all.length > 0)
            focusTarget(all[0]).forceActiveFocus()
        else
            root.forceActiveFocus()
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.32
        TapHandler { onTapped: root.closeRequested() }
    }
    Rectangle {
        id: card
        objectName: "sheetCard"
        width: root.cardWidth
        height: Math.min(root.height - (root.phone ? 24 : 48), root.chrome + body.implicitHeight)
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: root.phone ? undefined : parent.verticalCenter
        anchors.bottom: root.phone ? parent.bottom : undefined
        color: pal.surfaceContainerHigh
        radius: 28
        // A bottom sheet is square where it meets the screen edge.
        Rectangle {
            visible: root.phone
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 28
            color: parent.color
        }
        border.width: root.highContrast ? 1.5 : 0
        border.color: pal.outline
        // Takes the clicks so the scrim's tap handler does not see them.
        TapHandler { }

        Rectangle {
            visible: root.phone
            x: (parent.width - 32) / 2
            y: 12
            width: 32
            height: 4
            radius: 2
            color: pal.outline
        }
        Text {
            id: titleText
            objectName: "sheetTitle"
            x: root.margin
            y: root.phone ? 32 : 24
            width: card.width - 2 * root.margin
            text: root.heading
            color: pal.inkSurface
            font.family: M3Font.family
            font.pixelSize: 24
            font.weight: 400
            wrapMode: Text.WordWrap
        }
        Flickable {
            id: scroller
            objectName: "sheetBody"
            x: root.margin
            y: titleText.y + titleText.height + 16
            width: card.width - 2 * root.margin
            height: card.height - y - 16 - footer.height - 24
            contentWidth: width
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // The ring of a focused field sits 4px outside it; the padding keeps it from being cut.
            Column {
                id: body
                x: 4
                width: scroller.width - 8
                spacing: 16
            }
        }
        Item {
            id: footer
            x: root.margin
            width: card.width - 2 * root.margin
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            height: 40
            Row { id: leadingRow; anchors.left: parent.left; spacing: 8 }
            Row { id: trailingRow; anchors.right: parent.right; spacing: 8 }
        }
    }

    Accessible.role: Accessible.Dialog
    Accessible.name: accessName !== "" ? accessName : heading
    // BeforeItem: TextInput swallows Tab, and the window's tab chain leaves the sheet on Backtab.
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
