import QtQuick

// A small month under the Week or Month title, for going to a date. It is the Day side panel's
// MiniMonth with month buttons; Esc and a tap outside close it, and PageUp and PageDown change month.
FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: false
    property int year: 2026
    property int month: 11
    // Today's date, so that the month shows its disc when it is the one on view.
    property string todayIso: ""
    signal picked(string iso)
    signal closed()

    visible: open
    enabled: open
    Accessible.role: Accessible.Pane
    Accessible.name: "Go to a date"

    M3Palette { id: palette; theme: root.theme }

    function pad(value) {
        return value < 10 ? "0" + value : "" + value
    }

    function show(anchorIso, today) {
        var parts = anchorIso.split("-")
        root.year = parseInt(parts[0])
        root.month = parseInt(parts[1])
        root.todayIso = today
        root.open = true
        Qt.callLater(function() {
            mini.cursor = parseInt(parts[2])
            mini.forceActiveFocus()
        })
    }

    function step(delta) {
        var index = root.year * 12 + (root.month - 1) + delta
        root.year = Math.floor(index / 12)
        root.month = index % 12 + 1
        Qt.callLater(function() { mini.cursor = 1 })
    }

    function close() {
        if (!root.open)
            return
        root.open = false
        root.closed()
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape) {
            root.close()
        } else if (event.key === Qt.Key_PageUp) {
            root.step(-1)
        } else if (event.key === Qt.Key_PageDown) {
            root.step(1)
        } else {
            return
        }
        event.accepted = true
    }

    // Takes the tap, so a click outside only closes the picker.
    Item {
        anchors.fill: parent
        TapHandler {
            gesturePolicy: TapHandler.WithinBounds
            onTapped: root.close()
        }
    }

    Rectangle {
        id: card
        x: 12
        y: 4
        width: mini.width + 24
        height: mini.height + 24
        radius: 16
        color: palette.surfaceContainer
        border.width: root.highContrast ? 1.5 : 0
        border.color: palette.outlineVariant

        TapHandler { gesturePolicy: TapHandler.WithinBounds }

        MiniMonth {
            id: mini
            objectName: "datePickerMonth"
            x: 12
            y: 12
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            year: root.year
            month: root.month
            today: root.todayIso.slice(0, 7) === root.year + "-" + root.pad(root.month)
                   ? parseInt(root.todayIso.slice(8, 10)) : 0
            accessName: "Go to a date"
            onDayActivated: (day) => {
                root.open = false
                root.picked(root.year + "-" + root.pad(root.month) + "-" + root.pad(day))
                root.closed()
            }
        }

        IconButton {
            objectName: "datePickerPrevious"
            small: true
            x: card.width - 12 - 64
            y: 6
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: "chevron_left"
            accessName: "Previous month"
            onClicked: root.step(-1)
        }

        IconButton {
            objectName: "datePickerNext"
            small: true
            x: card.width - 12 - 32
            y: 6
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            icon: "chevron_right"
            accessName: "Next month"
            onClicked: root.step(1)
        }
    }
}
