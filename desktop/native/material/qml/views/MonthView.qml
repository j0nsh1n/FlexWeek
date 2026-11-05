import QtQuick
import components 1.0
import month 1.0

Item {
    id: root
    objectName: "materialMonth"
    property var bridge
    property bool phone: false
    property bool passive: false
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false
    readonly property bool narrow: phone
    readonly property var month: bridge ? bridge.month : null
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape && root.month && root.month.barOpen) {
            root.month.closeDate()
            event.accepted = true
        }
    }

    // The shell's number-key test reads this. The top bar already names the month.
    Text {
        objectName: "screenTitle"
        visible: false
        text: "Month"
    }

    Item {
        anchors.fill: parent
        anchors.margins: 12
        anchors.bottomMargin: 12 + (root.phone ? 96 : 0)

        Item {
            id: tools
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 48

            IconButton {
                id: prevMonth
                objectName: "monthPrev"
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "chevron_left"
                accessName: "Previous month"
                visible: !root.passive
                activeFocusOnTab: !root.passive
                onClicked: if (root.month) root.month.previousMonth()
            }

            IconButton {
                id: nextMonth
                objectName: "monthNext"
                anchors.left: prevMonth.right
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "chevron_right"
                accessName: "Next month"
                visible: !root.passive
                activeFocusOnTab: !root.passive
                onClicked: if (root.month) root.month.nextMonth()
            }

            Switch {
                id: studySwitch
                objectName: "monthStudyTime"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                checked: root.month ? root.month.showStudyTime : false
                accessName: root.month ? root.month.studyLabel : "Show study time per date"
                visible: !root.passive
                activeFocusOnTab: !root.passive
                onToggled: (on) => {
                    if (root.month)
                        root.month.setShowStudyTime(on)
                    // Switch.toggle writes `checked`, which drops the binding; put it back.
                    checked = Qt.binding(function() { return root.month ? root.month.showStudyTime : false })
                }
            }

            Text {
                objectName: "monthStudyCaption"
                anchors.left: nextMonth.right
                anchors.leftMargin: 12
                anchors.right: studySwitch.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: root.month ? root.month.studyLabel : ""
                color: tones.inkMuted
                font.family: M3Font.family
                font.pixelSize: 13
                font.weight: 500
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
                visible: !root.passive
            }
        }

        Row {
            id: heads
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: tools.bottom
            height: 24

            Repeater {
                model: root.month ? root.month.weekdays : 0

                Text {
                    objectName: "monthWeekday"
                    width: heads.width / 7
                    height: 24
                    text: model.label
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    color: tones.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: 12
                    font.weight: 500
                }
            }
        }

        DateBar {
            id: bar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: root.month ? root.month.barOpen : false
            height: visible ? implicitHeight : 0
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            heading: root.month ? root.month.heading : ""
            lines: root.month ? root.month.lines : null
            onCloseRequested: if (root.month) root.month.closeDate()
            onOpenRequested: if (root.month) root.month.openDay()
        }

        Item {
            id: board
            objectName: "monthGrid"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: heads.bottom
            anchors.topMargin: 8
            anchors.bottom: bar.visible ? bar.top : parent.bottom
            anchors.bottomMargin: bar.visible ? 8 : 0

            readonly property int columns: 7
            readonly property int count: dates.count
            readonly property int rows: Math.max(1, Math.ceil(count / columns))
            readonly property real gap: 6
            readonly property real cellW: count > 0 ? (width - gap * (columns - 1)) / columns : 0
            readonly property real cellH: count > 0
                    ? Math.max(root.narrow ? 52 : 68, (height - gap * (rows - 1)) / rows)
                    : 0

            Repeater {
                id: dates
                model: root.month ? root.month.dates : 0

                MonthCell {
                    x: (index % board.columns) * (board.cellW + board.gap)
                    y: Math.floor(index / board.columns) * (board.cellH + board.gap)
                    width: board.cellW
                    height: board.cellH
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    iso: model.iso
                    day: model.day
                    inMonth: model.inMonth
                    today: model.today
                    picked: root.month ? root.month.selectedIso === model.iso : false
                    narrow: root.narrow
                    showStudy: root.month ? root.month.showStudyTime : false
                    chipsJson: model.chipsJson
                    plannedShare: model.plannedShare
                    completedShare: model.completedShare
                    accessName: model.accessName
                    passive: root.passive
                    onChosen: (dayIso) => { if (root.month) root.month.selectDate(dayIso) }
                    onStep: (delta) => board.focusDate(index + delta)
                }
            }

            function focusDate(next) {
                if (next < 0 || next >= dates.count)
                    return
                var item = dates.itemAt(next)
                if (item)
                    item.forceActiveFocus()
            }
        }
    }

    M3Palette { id: tones; theme: root.theme }
}
