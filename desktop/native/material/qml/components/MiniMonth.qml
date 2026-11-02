import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property int year: 2026
    property int month: 11
    property int today: 5
    property string accessName: "Month"
    signal dayActivated(int day)

    readonly property int cell: 28
    implicitWidth: 7 * cell + 12
    implicitHeight: caption.implicitHeight + 8 + 7 * cell
    width: implicitWidth
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    // A repeater delegate has its own `palette`, so colours are copied onto the root.
    readonly property color muteInk: palette.inkMuted
    readonly property color dayInk: palette.inkSurface
    readonly property color todayFill: palette.primary
    readonly property color todayInk: palette.inkPrimary
    readonly property color focusRing: palette.primary
    property int cursor: today

    onTodayChanged: if (!activeFocus)
        cursor = today
    onYearChanged: if (!activeFocus)
        cursor = today
    onMonthChanged: if (!activeFocus)
        cursor = today

    function monthName() {
        var names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        return names[month - 1] + " " + year
    }

    function daysInMonth() {
        return new Date(year, month, 0).getDate()
    }

    // The month before this one. November 2026's grid opens on 26 October.
    function previousLength() {
        return new Date(year, month - 1, 0).getDate()
    }

    // Monday is column 0, matching the mockup's M T W T F S S.
    function lead() {
        var js = new Date(year, month - 1, 1).getDay()
        return (js + 6) % 7
    }

    function dayAt(index) {
        return index - lead() + 1
    }

    Text {
        id: caption
        text: root.monthName()
        color: root.muteInk
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
    }

    Repeater {
        model: 7
        delegate: Text {
            x: index * root.cell
            y: caption.height + 4
            width: root.cell
            height: root.cell
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: ["M", "T", "W", "T", "F", "S", "S"][index]
            color: root.muteInk
            font.family: M3Font.family
            font.pixelSize: 12
            font.weight: 500
        }
    }

    Repeater {
        model: 42
        delegate: Item {
            id: cell
            readonly property int day: root.dayAt(index)
            readonly property bool inside: day >= 1 && day <= root.daysInMonth()
            readonly property bool isToday: inside && day === root.today
            x: (index % 7) * root.cell
            y: caption.height + 4 + root.cell + Math.floor(index / 7) * root.cell
            width: root.cell
            height: root.cell
            opacity: inside ? 1 : 0.4
            readonly property bool isCursor: cell.inside && cell.day === root.cursor && root.activeFocus
            Rectangle {
                objectName: cell.isToday ? "todayDisc" : ""
                visible: cell.isToday
                width: 28
                height: 28
                radius: 14
                anchors.centerIn: parent
                color: root.todayFill
            }
            M3FocusRing {
                objectName: cell.isCursor ? "cursorRing" : ""
                anchors.fill: parent
                anchors.margins: -2
                shown: cell.isCursor
                ring: root.focusRing
                ringRadius: 16
            }
            Text {
                objectName: "cell" + index
                anchors.centerIn: parent
                text: {
                    if (cell.inside)
                        return cell.day
                    if (cell.day < 1)
                        return root.previousLength() + cell.day
                    return cell.day - root.daysInMonth()
                }
                color: cell.isToday ? root.todayInk : root.dayInk
                font.family: M3Font.family
                font.pixelSize: 12
                font.weight: cell.isToday ? 500 : 400
                Accessible.role: Accessible.StaticText
                Accessible.name: cell.inside ? String(cell.day) : ""
                Accessible.ignored: !cell.inside
            }
            TapHandler {
                enabled: cell.inside
                onTapped: {
                    root.cursor = cell.day
                    root.dayActivated(cell.day)
                }
            }
        }
    }

    function move(step) {
        var next = cursor + step
        if (next < 1)
            next = 1
        if (next > daysInMonth())
            next = daysInMonth()
        cursor = next
    }

    activeFocusOnTab: true
    Accessible.role: Accessible.Table
    Accessible.name: (accessName !== "" ? accessName : monthName()) + ", " + cursor
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Right)
            root.move(1)
        else if (event.key === Qt.Key_Left)
            root.move(-1)
        else if (event.key === Qt.Key_Down)
            root.move(7)
        else if (event.key === Qt.Key_Up)
            root.move(-7)
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space)
            root.dayActivated(root.cursor)
        else
            return
        event.accepted = true
    }
}
