import QtQuick
import components 1.0
import day 1.0

Item {
    id: root
    objectName: "materialMyDay"
    property var bridge
    property bool phone: false
    // The shell's page heading, where keyboard focus goes when the Now card goes away holding it.
    property Item pageHeading: null

    readonly property var board: bridge && bridge.myday ? bridge.myday : null
    readonly property var theme: bridge && bridge.theme ? bridge.theme : ({})
    readonly property string density: bridge && bridge.density ? bridge.density : "comfortable"
    readonly property bool reduceMotion: bridge ? bridge.reduceMotion : false
    readonly property bool highContrast: bridge ? bridge.highContrast : false
    readonly property bool hasStatus: !!(board && (board.waiting || board.loadError))
    readonly property bool showNow: !!(board && board.showNow)

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
        contentHeight: column.implicitHeight + (root.phone ? 96 : 36)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column
            width: Math.min(1040, Math.max(0, pane.width - (root.phone ? 32 : 48)))
            x: Math.max(root.phone ? 16 : 24, (pane.width - width) / 2)
            y: root.phone ? 16 : 24
            spacing: 18

            Text {
                objectName: "myDayStatus"
                width: column.width
                visible: root.hasStatus
                text: root.board && root.board.waiting ? "Loading…" : (root.board ? root.board.loadError : "")
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(16)
                Accessible.role: Accessible.StaticText
                Accessible.name: text
            }

            // Unified Option B horizontal hero banner (progress ring + Now copy + action).
            NowCard {
                width: column.width
                shown: root.showNow && !root.hasStatus
                hero: true
                showRing: true
                narrow: root.phone
                ringShare: root.board ? root.board.ringShare : 0
                ringCount: root.board ? root.board.ringCount : 0
                ringCaption: root.board ? root.board.ringCaption : ""
                pageHeading: root.pageHeading
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
                busy: !!(root.board && root.board.nowBusy)
                line: root.board ? root.board.nowLine : ""
                onStartFocus: if (root.board) root.board.startFocus()
                onMarkFinished: if (root.board) root.board.markFinished()
                onStartAgain: if (root.board) root.board.startAgain()
                onDismissFinished: if (root.board) root.board.dismissFinished()
            }

            // Calm fallback banner carrying the ring when free-time nudges hide the Now card.
            Rectangle {
                id: ringFallback
                objectName: "myDayRingBanner"
                visible: !root.showNow && !root.hasStatus
                width: column.width
                implicitHeight: fallbackRow.implicitHeight + 36
                height: implicitHeight
                radius: palette.cornerFor(20)
                color: palette.cardSurface
                border.width: root.highContrast ? 1.5 : 1
                border.color: root.highContrast ? palette.outline : palette.outlineVariant

                Row {
                    id: fallbackRow
                    anchors.centerIn: parent
                    spacing: 20
                    ProgressRing {
                        objectName: ringFallback.visible ? "myDayRing" : ""
                        countName: ringFallback.visible ? "myDayCount" : ""
                        captionName: ringFallback.visible ? "myDayCaption" : ""
                        size: 132
                        theme: root.theme
                        share: root.board ? root.board.ringShare : 0
                        count: root.board ? root.board.ringCount : 0
                        caption: root.board ? root.board.ringCaption : ""
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: !!(root.board && root.board.leftLine)
                        text: root.board ? root.board.leftLine : ""
                        color: palette.inkSurface
                        font.family: M3Font.heading
                        font.pixelSize: M3Font.px(20)
                        font.weight: 500
                    }
                }
            }

            DayLists {
                width: column.width
                sideBySide: !root.phone && column.width >= 680
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
