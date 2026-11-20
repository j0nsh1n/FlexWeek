import QtQuick
import components 1.0

// A question with buttons: "Discard your changes?", a delete that asks first.
SheetFrame {
    id: root
    property var sheets
    readonly property var ask: sheets ? sheets.ask : ({})
    heading: ask.title ? ask.title : ""
    initialFocus: firstButton
    objectName: "sheetPrompt"
    onCloseRequested: sheets.closeSheet()
    M3Palette { id: pal; theme: root.theme }

    // Modal input catcher under the dialog card: absorbs clicks across the screen
    MouseArea {
        parent: root
        anchors.fill: parent
        z: 0
        preventStealing: true
        onClicked: root.closeRequested()
    }

    property int pick: 0
    readonly property var cards: ask.cards ? ask.cards : []
    readonly property bool choosing: cards.length > 0
    // A card is destructive when its answer is (This week and later): it marks itself in the error colour
    // when picked, and Confirm is red only while such a card is picked.
    function cardIsDanger(id) {
        var answers = ask.answers ? ask.answers : []
        for (var i = 0; i < answers.length; i++)
            if (answers[i].id === id)
                return answers[i].kind === "danger"
        return false
    }
    readonly property bool pickedDanger: choosing && pick >= 0 && pick < cards.length && cardIsDanger(cards[pick].id)
    readonly property var footerAnswers: choosing
        ? [{ "id": "stay", "label": "Cancel", "kind": "text" },
           { "id": "confirm", "label": ask.confirm ? ask.confirm : "OK",
             "kind": "filled", "default": true }]
        : (ask.answers ? ask.answers : [])
    // A prompt names the card picked first when the safe answer is not the first card.
    onAskChanged: pick = ask.pick !== undefined ? ask.pick : 0

    function movePick(step) {
        if (cards.length > 0)
            pick = Math.max(0, Math.min(cards.length - 1, pick + step))
    }
    function confirmPick() {
        if (choosing)
            sheets.answer(cards[pick].id)
    }

    Keys.onUpPressed: (event) => {
        root.movePick(-1)
        event.accepted = root.choosing
    }
    Keys.onDownPressed: (event) => {
        root.movePick(1)
        event.accepted = root.choosing
    }

    Text {
        visible: text !== ""
        width: parent.width
        text: root.ask.body ? root.ask.body : ""
        color: pal.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
    Column {
        id: cardList
        objectName: "promptCards"
        visible: root.choosing
        width: parent.width
        spacing: 8
        Repeater {
            model: root.cards
            delegate: Rectangle {
                id: card
                objectName: "prompt_card_" + modelData.id
                readonly property bool picked: root.pick === index
                readonly property color accent: root.cardIsDanger(modelData.id) ? pal.error : pal.primary
                width: cardList.width
                height: cardText.implicitHeight + 24
                radius: 14
                color: picked ? Qt.tint(pal.surfaceContainerHighest, Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.14))
                              : pal.surfaceContainerHighest
                border.width: picked ? 2 : 1
                border.color: picked ? card.accent : pal.outlineVariant
                Accessible.role: Accessible.RadioButton
                readonly property string spoken: modelData.title + ". " + modelData.line + (picked ? " Picked." : " Not picked.")
                Accessible.name: spoken
                Accessible.checkable: true
                Accessible.checked: picked
                Accessible.onPressAction: root.pick = index
                TapHandler { onTapped: root.pick = index }
                Column {
                    id: cardText
                    x: 16
                    y: 12
                    width: parent.width - 16 - badge.width - 12 - 16
                    spacing: 2
                    Text {
                        objectName: "promptCardTitle"
                        width: parent.width
                        text: modelData.title
                        color: pal.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(16)
                        font.weight: 500
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        width: parent.width
                        text: modelData.line
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        wrapMode: Text.WordWrap
                    }
                }
                // A ring that fills with a check, so the pick is not shown by colour alone.
                Rectangle {
                    id: badge
                    objectName: "promptCardBadge"
                    width: M3Font.px(22)
                    height: width
                    radius: width / 2
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    color: card.picked ? card.accent : "transparent"
                    border.width: card.picked ? 0 : 2
                    border.color: pal.outline
                    M3Icon {
                        visible: card.picked
                        anchors.centerIn: parent
                        width: parent.width - 6
                        height: width
                        name: "check"
                        color: root.cardIsDanger(modelData.id) ? pal.inkError : pal.inkPrimary
                    }
                }
            }
        }
    }
    trailing: Repeater {
        model: root.footerAnswers
        delegate: Button {
            id: choice
            objectName: "prompt_" + modelData.id
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            // Confirm turns red with the pick, without rebuilding the footer (which would drop the keyboard).
            kind: modelData.id === "confirm" && root.pickedDanger ? "danger" : modelData.kind
            text: modelData.label
            accessName: modelData.label
            onClicked: modelData.id === "confirm" ? root.confirmPick() : root.sheets.answer(modelData.id)
            Component.onCompleted: {
                if (modelData["default"] === true)
                    root.firstButton = choice
                else if (index === 0 && root.firstButton === null)
                    root.firstButton = choice
            }
        }
    }
    property Item firstButton: null
}
