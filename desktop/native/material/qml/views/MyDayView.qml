import QtQuick
import components 1.0
import day 1.0

Item {
    id: root
    objectName: "materialMyDay"
    property var bridge
    property bool phone: false

    readonly property var board: bridge && bridge.myday ? bridge.myday : null
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge && bridge.density ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false

    M3Palette { id: palette; theme: root.theme }

    // The page's heading for screen readers. The top bar already shows the title.
    Text {
        objectName: "screenTitle"
        width: 1
        height: 1
        opacity: 0
        text: "My day"
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        Accessible.role: Accessible.Heading
        Accessible.name: text
    }

    Flickable {
        id: pane
        anchors.fill: parent
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

            Text {
                objectName: "myDayStatus"
                width: column.width
                visible: root.board && (root.board.waiting || root.board.loadError)
                text: root.board && root.board.waiting ? "Loading…" : (root.board ? root.board.loadError : "")
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(16)
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }

            Item {
                width: column.width
                height: ring.height
                visible: !(root.board && (root.board.waiting || root.board.loadError))
                ProgressRing {
                    id: ring
                    anchors.horizontalCenter: parent.horizontalCenter
                    theme: root.theme
                    share: root.board ? root.board.ringShare : 0
                    count: root.board ? root.board.ringCount : 0
                    caption: root.board ? root.board.ringCaption : ""
                }
            }

            NowCard {
                width: column.width
                visible: root.board && root.board.showNow
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                timerTitle: root.board ? root.board.timerTitle : ""
                timerLine: root.board ? root.board.timerLine : ""
                timerEnded: root.board ? root.board.timerEnded : false
                timerCanFinish: root.board ? root.board.timerCanFinish : false
                timerDone: root.board ? root.board.timerDone : false
                scope: "myDay"
                title: root.board ? root.board.nowTitle : ""
                focusTitle: root.board ? root.board.focusTitle : ""
                line: root.board ? root.board.nowLine : ""
                onStartFocus: if (root.board) root.board.startFocus()
                onMarkFinished: if (root.board) root.board.markFinished()
                onStartAgain: if (root.board) root.board.startAgain()
                onDismissFinished: if (root.board) root.board.dismissFinished()
            }

            DayLists {
                width: column.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                scope: "myDay"
                upModel: root.board ? root.board.upNext : null
                doneModel: root.board ? root.board.doneRows : null
                onFinish: (assignmentId) => {
                    if (root.board)
                        root.board.finishHomework(assignmentId)
                }
            }
        }
    }
}
