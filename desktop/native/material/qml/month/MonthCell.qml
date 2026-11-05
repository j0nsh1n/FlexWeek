import QtQuick
import components 1.0

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string iso: ""
    property int day: 1
    property bool inMonth: true
    property bool today: false
    property bool picked: false
    property bool narrow: false
    property bool showStudy: false
    property string chipsJson: "[]"
    property real plannedShare: 0
    property real completedShare: 0
    property string accessName: ""
    property bool passive: false
    signal chosen(string iso)
    signal step(int delta)

    objectName: "monthDate-" + iso
    opacity: inMonth ? 1 : 0.45
    activeFocusOnTab: !passive
    Accessible.role: Accessible.Button
    Accessible.name: accessName
    Accessible.onPressAction: root.chosen(root.iso)

    property var chipShown: []
    property var dotShown: []
    property int extra: 0

    // Chips are 16px with 2px between, under the day number. What does not fit becomes "and N more".
    readonly property int rowsFit: Math.max(1, Math.min(4, Math.floor((height - 34) / 18)))

    function _refreshChips() {
        var all = []
        try {
            all = JSON.parse(chipsJson)
        } catch (e) {
            all = []
        }
        // One line still keeps a chip; "and N more" sits by the day number, as Widgets month does.
        var room = all.length <= rowsFit ? all.length : Math.max(1, rowsFit - 1)
        var chips = []
        var dots = []
        for (var i = 0; i < all.length; i++) {
            if (i < room)
                chips.push(all[i])
            if (i < 4)
                dots.push(all[i])
        }
        chipShown = chips
        dotShown = dots
        extra = all.length - chips.length
    }

    onChipsJsonChanged: _refreshChips()
    onRowsFitChanged: _refreshChips()
    Component.onCompleted: _refreshChips()

    M3Palette { id: tones; theme: root.theme }

    readonly property var homeworkClass: {
        var cls = tones.classes
        if (cls && cls.assignments)
            return cls.assignments
        return { bar: "#a87512", fill: tones.surfaceContainerHighest, ink: tones.inkMuted }
    }

    Rectangle {
        id: card
        objectName: "monthCellFill"
        anchors.fill: parent
        radius: 12
        color: root.picked ? tones.secondaryContainer : tones.surfaceContainerLow
        border.width: root.highContrast ? 1.5 : 0
        border.color: tones.outline
        Behavior on color {
            ColorAnimation {
                duration: root.reduceMotion ? 0 : 200
                easing.type: Easing.BezierSpline
                easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
            }
        }
    }

    M3StateLayer {
        anchors.fill: parent
        radius: 12
        color: tones.inkSurface
        hovered: hover.hovered
        down: tap.pressed || root.keyDown
        reduceMotion: root.reduceMotion
    }

    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -2
        target: root
        ring: tones.primary
        ringRadius: 14
    }

    Rectangle {
        objectName: "monthToday"
        visible: root.today
        x: 6
        y: 4
        width: 24
        height: 24
        radius: 12
        color: tones.primary
    }

    Text {
        objectName: "monthDayNumber"
        x: 6
        y: 4
        width: 24
        height: 24
        text: root.day
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: root.today ? tones.inkPrimary : tones.inkSurface
        font.family: M3Font.family
        font.pixelSize: 13
        font.weight: 500
    }

    Text {
        objectName: "monthMore"
        visible: !root.narrow && root.extra > 0 && root.rowsFit === 1
        x: 32
        y: 4
        height: 24
        width: Math.max(0, parent.width - 36)
        text: "and " + root.extra + " more"
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        color: tones.inkMuted
        font.family: M3Font.family
        font.pixelSize: 11
        font.weight: 500
    }

    Item {
        objectName: "monthStudyBar"
        visible: root.showStudy && (root.plannedShare > 0 || root.completedShare > 0)
        x: 6
        y: 30
        width: Math.max(0, parent.width - 12)
        height: 3

        Rectangle {
            width: parent.width * root.plannedShare
            height: 3
            radius: 1
            color: tones.primaryContainer
        }

        Rectangle {
            width: parent.width * root.completedShare
            height: 3
            radius: 1
            color: tones.primary
        }
    }

    Column {
        visible: !root.narrow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 32
        anchors.bottom: parent.bottom
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        spacing: 2
        clip: true

        Repeater {
            model: root.chipShown

            Rectangle {
                id: chipBody
                objectName: "monthChip"
                required property var modelData
                readonly property bool due: modelData.kind === "due"
                readonly property bool overdue: modelData.kind === "overdue"
                readonly property color chipFill: overdue
                    ? tones.statusOverdueTint
                    : (due ? homeworkClass.fill : tones.surfaceContainerHighest)
                readonly property color chipInk: overdue
                    ? tones.statusOverdue
                    : (due ? homeworkClass.ink : tones.inkMuted)
                readonly property string chipIcon: overdue ? "warning" : (due ? "edit_note" : "")
                width: parent.width
                height: 16
                radius: height / 2
                color: chipFill

                Rectangle {
                    objectName: "monthChipBar"
                    visible: chipBody.due
                    width: 3
                    height: parent.height
                    color: homeworkClass.bar
                    topLeftRadius: parent.radius
                    bottomLeftRadius: parent.radius
                }

                Row {
                    id: chipRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: chipBody.due ? 5 : 4
                    anchors.rightMargin: 4
                    spacing: 2

                    M3Icon {
                        objectName: "monthChipIcon"
                        visible: chipBody.chipIcon !== ""
                        name: chipBody.chipIcon
                        width: 12
                        height: 12
                        anchors.verticalCenter: parent.verticalCenter
                        color: chipBody.chipInk
                    }

                    Text {
                        objectName: "monthChipText"
                        width: Math.max(0, chipRow.width - (chipBody.chipIcon !== "" ? 14 : 0))
                        height: 16
                        text: modelData.text
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        color: chipBody.chipInk
                        font.family: M3Font.family
                        font.pixelSize: 11
                        font.weight: 500
                    }
                }

                Accessible.role: Accessible.StaticText
                Accessible.name: modelData.text
            }
        }

        Text {
            objectName: "monthMore"
            visible: root.extra > 0 && root.rowsFit > 1
            width: parent.width
            text: "and " + root.extra + " more"
            color: tones.inkMuted
            font.family: M3Font.family
            font.pixelSize: 11
            font.weight: 500
        }
    }

    Row {
        objectName: "monthDots"
        visible: root.narrow && root.dotShown.length > 0
        anchors.left: parent.left
        anchors.leftMargin: 6
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        spacing: 3

        Repeater {
            model: root.dotShown

            Rectangle {
                objectName: "monthDot"
                required property var modelData
                width: 6
                height: 6
                radius: 3
                // The same colours as the wide chips: homework's bar, the overdue status, else muted.
                color: modelData.kind === "overdue"
                       ? tones.statusOverdue
                       : modelData.kind === "due"
                         ? root.homeworkClass.bar
                         : tones.inkMuted
                Accessible.role: Accessible.StaticText
                Accessible.name: modelData.text
            }
        }
    }

    property bool keyDown: false
    HoverHandler { id: hover }
    TapHandler {
        id: tap
        onTapped: root.chosen(root.iso)
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        } else if (event.key === Qt.Key_Left) {
            root.step(-1)
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            root.step(1)
            event.accepted = true
        } else if (event.key === Qt.Key_Up) {
            root.step(-7)
            event.accepted = true
        } else if (event.key === Qt.Key_Down) {
            root.step(7)
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown)
                root.chosen(root.iso)
            root.keyDown = false
            event.accepted = true
        }
    }
}
