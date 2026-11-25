import QtQuick
import components 1.0

Column {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool passive: false
    // A running focus timer: the card names it and its button goes back to it.
    property string timerTitle: ""
    property string timerLine: ""
    // The timer has run out and is not cleared: the card says so and offers Mark finished (when the
    // homework is still open) and Start again.
    property bool timerEnded: false
    property bool timerCanFinish: false
    // The timer has run out on homework that is already done: the one button is OK, which clears it.
    property bool timerDone: false
    property string scope: "day"
    property string title: ""
    property string line: ""
    // The homework Start focus opens; the free-time card does not name it anywhere else.
    property string focusTitle: ""
    // A fixed block such as Soccer is on: the card says until when and what is next, and starts nothing.
    property bool busy: false
    // Horizontal hero layout (My day Option B): ring on the left, Now copy in the middle, action on the right.
    property bool hero: false
    property bool showRing: false
    property real ringShare: 0
    property int ringCount: 0
    property string ringCaption: ""
    property bool narrow: false
    signal startFocus()
    signal markFinished()
    signal startAgain()
    signal dismissFinished()

    spacing: 0
    width: parent ? parent.width : implicitWidth

    M3Palette { id: palette; theme: root.theme }

    // Whether the card has something to show. The card hides once the timer clears and nothing else is
    // on today; a page that is merely not on screen does not count.
    property bool shown: true
    // The page's heading: keyboard focus goes there when the card goes away while one of its buttons holds it.
    property Item pageHeading: null
    visible: shown

    // Qt takes focus off a button as it hides, which can come before or after shownChanged reaches
    // this card, so both the card and its buttons hand focus on; whichever runs second finds it done.
    function handFocusToHeading() {
        // Also when the card stays but its Start button hides, as the clock moves into a fixed block.
        if ((!root.shown || !startButton.visible) && root.pageHeading)
            root.pageHeading.forceActiveFocus()
    }
    onShownChanged: if (startButton.activeFocus || markButton.activeFocus) handFocusToHeading()

    readonly property bool wideHero: root.hero && !root.narrow && card.width >= 600
    readonly property bool hasActions: startButton.visible || markButton.visible

    Rectangle {
        id: card
        objectName: root.scope + "Now"
        width: parent.width
        readonly property int pad: root.density === "compact" ? 16 : (root.hero ? 24 : 20)
        readonly property real innerWidth: Math.max(0, width - pad * 2)
        readonly property real actionsWidth: (markButton.visible ? markButton.implicitWidth : 0)
            + (markButton.visible && startButton.visible ? 8 : 0)
            + (startButton.visible ? startButton.implicitWidth : 0)
        readonly property real stackedHeight: stackColumn.implicitHeight + (root.hasActions ? 14 + actionFlow.implicitHeight : 0)
        readonly property real heroHeight: Math.max(
            root.showRing ? heroRingWrap.height : 0,
            heroTextCol.implicitHeight,
            root.hasActions ? actionFlow.implicitHeight : 0
        )
        implicitHeight: (root.wideHero ? heroHeight : stackedHeight) + pad * 2
        height: implicitHeight
        radius: palette.cornerFor(20)
        color: palette.primaryContainer
        border.width: root.highContrast ? 1.5 : 1
        border.color: root.highContrast ? palette.outline : Qt.rgba(palette.primary.r, palette.primary.g, palette.primary.b, 0.22)
        Accessible.role: Accessible.Grouping
        Accessible.name: (root.timerTitle || root.title) + ", " + (root.timerTitle ? root.timerLine : root.line)

        // Wide horizontal hero content (My day desktop)
        Item {
            id: heroRow
            visible: root.wideHero
            x: card.pad
            y: card.pad
            width: card.innerWidth
            height: card.heroHeight

            Rectangle {
                id: heroRingWrap
                visible: root.showRing
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: root.showRing ? 148 : 0
                height: 148
                radius: 74
                color: palette.cardSurface
                ProgressRing {
                    id: heroRing
                    objectName: root.wideHero && root.showRing ? "myDayRing" : ""
                    countName: root.wideHero && root.showRing ? "myDayCount" : ""
                    captionName: root.wideHero && root.showRing ? "myDayCaption" : ""
                    anchors.centerIn: parent
                    size: 132
                    theme: root.theme
                    share: root.ringShare
                    count: root.ringCount
                    caption: root.ringCaption
                }
            }

            Column {
                id: heroTextCol
                anchors.left: root.showRing ? heroRingWrap.right : parent.left
                anchors.leftMargin: root.showRing ? 24 : 0
                width: Math.max(
                    120,
                    heroRow.width
                    - (root.showRing ? heroRingWrap.width + 24 : 0)
                    - (root.hasActions ? card.actionsWidth + 20 : 0)
                )
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                Row {
                    spacing: 6
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        anchors.verticalCenter: parent.verticalCenter
                        color: palette.primary
                    }
                    Text {
                        objectName: root.wideHero ? root.scope + "NowLabel" : ""
                        text: "NOW"
                        color: palette.primary
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(11)
                        font.weight: 700
                        font.letterSpacing: 0.8
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Now"
                    }
                }
                Text {
                    objectName: root.wideHero ? root.scope + "NowTitle" : ""
                    width: parent.width
                    text: root.timerTitle || root.title
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(26)
                    font.weight: 600
                }
                Text {
                    objectName: root.wideHero ? root.scope + "NowLine" : ""
                    width: parent.width
                    text: root.timerTitle ? root.timerLine : root.line
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    opacity: 0.88
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(15)
                    font.weight: 400
                }
            }
        }

        // Stacked vertical content (Day sidebar & narrow My day)
        Column {
            id: stackColumn
            visible: !root.wideHero
            x: card.pad
            y: card.pad
            width: card.innerWidth
            spacing: 0

            Rectangle {
                id: stackRingWrap
                visible: root.showRing && !root.wideHero
                anchors.horizontalCenter: parent.horizontalCenter
                width: 148
                height: 148
                radius: 74
                color: palette.cardSurface
                ProgressRing {
                    objectName: !root.wideHero && root.showRing ? "myDayRing" : ""
                    countName: !root.wideHero && root.showRing ? "myDayCount" : ""
                    captionName: !root.wideHero && root.showRing ? "myDayCaption" : ""
                    anchors.centerIn: parent
                    size: 132
                    theme: root.theme
                    share: root.ringShare
                    count: root.ringCount
                    caption: root.ringCaption
                }
            }
            Item { width: 1; height: 14; visible: stackRingWrap.visible }

            Column {
                width: parent.width
                spacing: 4
                Row {
                    spacing: 6
                    Rectangle {
                        width: 7
                        height: 7
                        radius: 3.5
                        anchors.verticalCenter: parent.verticalCenter
                        color: palette.primary
                    }
                    Text {
                        objectName: !root.wideHero ? root.scope + "NowLabel" : ""
                        text: "NOW"
                        color: palette.primary
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(11)
                        font.weight: 700
                        font.letterSpacing: 0.8
                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Now"
                    }
                }
                Text {
                    objectName: !root.wideHero ? root.scope + "NowTitle" : ""
                    width: parent.width
                    text: root.timerTitle || root.title
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(22)
                    font.weight: 600
                }
                Text {
                    objectName: !root.wideHero ? root.scope + "NowLine" : ""
                    width: parent.width
                    text: root.timerTitle ? root.timerLine : root.line
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    opacity: 0.88
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    font.weight: 400
                }
            }
        }

        // Single static action flow so Tab / Shift+Tab order between Mark finished and Start stays intact.
        Flow {
            id: actionFlow
            visible: root.hasActions
            x: root.wideHero ? card.width - card.pad - width : card.pad
            y: root.wideHero
                ? card.pad + (card.heroHeight - height) / 2
                : card.pad + stackColumn.implicitHeight + 14
            width: root.wideHero ? card.actionsWidth : card.innerWidth
            spacing: 8

            Button {
                id: markButton
                objectName: root.scope + "MarkFinished"
                visible: root.timerEnded && root.timerCanFinish
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "filled"
                text: "Mark finished"
                icon: "check"
                accessName: text
                activeFocusOnTab: !root.passive
                // This button hides once the timer clears, so keyboard focus moves to the one that stays
                // before the card can hide (and hand focus on to the page) in markFinished().
                onClicked: { startButton.forceActiveFocus(); root.markFinished() }
                onActiveFocusChanged: if (!activeFocus) root.handFocusToHeading()
            }
            Button {
                id: startButton
                width: !root.wideHero && !(root.timerEnded && root.timerCanFinish) ? actionFlow.width : implicitWidth
                objectName: root.scope + "StartFocus"
                visible: !root.busy || root.timerTitle !== "" || root.timerEnded || root.timerDone
                // Qt keeps focus on a button that hides inside a card that stays, so hand it on here.
                onVisibleChanged: if (!visible && activeFocus) root.handFocusToHeading()
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: root.timerEnded && root.timerCanFinish ? "outlined" : "filled"
                text: root.timerDone ? "OK" : root.timerEnded ? "Start again"
                    : (root.timerTitle ? "Back to " + root.timerTitle : (root.focusTitle ? "Start " + root.focusTitle : "Start focus"))
                icon: root.timerDone ? "check" : "play_arrow"
                accessName: text
                activeFocusOnTab: !root.passive
                onActiveFocusChanged: if (!activeFocus) root.handFocusToHeading()
                // The button that was used holds the keyboard, so whatever it opens hands focus back to it.
                onClicked: {
                    forceActiveFocus()
                    if (root.timerDone) root.dismissFinished()
                    else if (root.timerEnded) root.startAgain()
                    else root.startFocus()
                }
            }
        }
    }
}
