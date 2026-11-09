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
    signal startFocus()
    signal markFinished()
    signal startAgain()
    signal dismissFinished()

    spacing: 8
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

    Text {
        objectName: root.scope + "NowLabel"
        text: "Now"
        color: palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        font.weight: 500
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    Rectangle {
        id: card
        objectName: root.scope + "Now"
        width: parent.width
        implicitHeight: column.implicitHeight + pad * 2
        height: implicitHeight
        radius: 8
        color: palette.primaryContainer
        Accessible.role: Accessible.Grouping
        Accessible.name: (root.timerTitle || root.title) + ", " + (root.timerTitle ? root.timerLine : root.line)

        readonly property int pad: root.density === "compact" ? 16 : 24

        Column {
            id: column
            x: card.pad
            y: card.pad
            width: card.width - card.pad * 2
            spacing: 0

            Column {
                width: parent.width
                spacing: 4
                Text {
                    objectName: root.scope + "NowTitle"
                    width: parent.width
                    text: root.timerTitle || root.title
                    wrapMode: Text.WordWrap
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(24)
                    font.weight: 400
                }
                Text {
                    objectName: root.scope + "NowLine"
                    width: parent.width
                    text: root.timerTitle ? root.timerLine : root.line
                    color: palette.inkPrimaryContainer
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(16)
                    font.weight: 400
                }
            }
            Item { width: 1; height: 12; visible: startButton.visible || markButton.visible }
            Flow {
                width: parent.width
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
}
