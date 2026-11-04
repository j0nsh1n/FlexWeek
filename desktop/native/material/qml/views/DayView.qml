import QtQuick
import components 1.0
import day 1.0

Item {
    id: root
    objectName: "materialDay"
    property var bridge
    property bool phone: false

    readonly property var board: bridge && bridge.day ? bridge.day : null
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge && bridge.density ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false

    // The page's heading for screen readers. The top bar already shows the title.
    Text {
        objectName: "screenTitle"
        width: 1
        height: 1
        opacity: 0
        text: "Day"
        font.family: M3Font.family
        font.pixelSize: 12
        Accessible.role: Accessible.Heading
        Accessible.name: text
    }

    MonthSide {
        id: side
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        phone: root.phone
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        board: root.board
        year: root.board ? root.board.year : 2026
        month: root.board ? root.board.month : 1
        today: root.board ? root.board.miniDay : 0
    }

    Flickable {
        id: pane
        anchors.left: side.visible ? side.right : parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        contentWidth: width
        contentHeight: column.implicitHeight + (root.phone ? 96 : 24)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column
            width: Math.min(760, Math.max(0, pane.width - (root.phone ? 32 : 48)))
            x: Math.max(root.phone ? 16 : 24, (pane.width - width) / 2)
            y: root.phone ? 16 : 24
            spacing: 12

            Row {
                spacing: 4
                IconButton {
                    objectName: "dayPrevious"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "chevron_left"
                    accessName: "Previous day"
                    onClicked: if (root.board) root.board.previousDay()
                }
                IconButton {
                    objectName: "dayNext"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "chevron_right"
                    accessName: "Next day"
                    onClicked: if (root.board) root.board.nextDay()
                }
            }

            Text {
                objectName: "dayLeftLine"
                width: column.width
                text: root.board ? root.board.leftLine : ""
                wrapMode: Text.WordWrap
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: 16
                font.weight: 400
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }

            NowCard {
                width: column.width
                visible: root.board && root.board.showNow
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                scope: "day"
                title: root.board ? root.board.nowTitle : ""
                line: root.board ? root.board.nowLine : ""
                onStartFocus: if (root.board) root.board.startFocus()
            }

            DayLists {
                width: column.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                scope: "day"
                upModel: root.board ? root.board.upNext : null
                doneModel: root.board ? root.board.doneRows : null
                onFinish: (assignmentId) => {
                    if (root.board)
                        root.board.finishHomework(assignmentId)
                }
            }
        }
    }

    M3Palette { id: palette; theme: root.theme }
}
