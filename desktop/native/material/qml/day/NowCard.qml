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
    signal startFocus()
    signal markFinished()
    signal startAgain()
    signal dismissFinished()

    spacing: 8
    width: parent ? parent.width : implicitWidth

    M3Palette { id: palette; theme: root.theme }

    // The whole card hides once the timer clears and nothing else is on today. Keyboard focus must not
    // stay on its hidden button: it goes to the first visible item the page's Tab order reaches.
    onVisibleChanged: {
        if (visible || !(startButton.activeFocus || markButton.activeFocus))
            return
        var item = startButton.nextItemInFocusChain(true)
        for (var i = 0; item && i < 200; i++) {
            if (item.visible && item.activeFocusOnTab && !card.contains(card.mapFromItem(item, 0, 0)) && item !== startButton) {
                item.forceActiveFocus()
                return
            }
            item = item.nextItemInFocusChain(true)
        }
    }

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
            Item { width: 1; height: 12 }
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
                }
                Button {
                    id: startButton
                    objectName: root.scope + "StartFocus"
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
