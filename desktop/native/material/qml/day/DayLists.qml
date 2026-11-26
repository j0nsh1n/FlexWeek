import QtQuick
import components 1.0

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool passive: false
    property bool sideBySide: false
    property string scope: "day"
    property var upModel
    property var doneModel
    signal finish(string assignmentId)
    signal edit(string assignmentId)

    width: parent ? parent.width : implicitWidth
    implicitHeight: layout.implicitHeight
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    readonly property color muted: palette.inkMuted
    readonly property int cardGap: 16
    readonly property real cardWidth: root.sideBySide
        ? Math.max(240, (width - cardGap) / 2)
        : width
    readonly property real balancedMinHeight: root.sideBySide
        ? Math.max(upInner.implicitHeight + 36, doneInner.implicitHeight + 36, 220)
        : 0

    // The done circle is sized as the one on a Week block: its title line tall, never under 20 px.
    FontMetrics {
        id: circleMetrics
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
        font.weight: 600
    }
    readonly property int circle: Math.max(20, Math.ceil(circleMetrics.height * 1.25))

    Grid {
        id: layout
        width: root.width
        columns: root.sideBySide ? 2 : 1
        columnSpacing: root.cardGap
        rowSpacing: root.cardGap

        // Up next card
        Rectangle {
            id: upCard
            objectName: root.scope + "UpNextCard"
            width: root.cardWidth
            implicitHeight: Math.max(upInner.implicitHeight + 36, root.balancedMinHeight)
            height: implicitHeight
            radius: palette.cornerFor(16)
            color: palette.cardSurface
            border.width: root.highContrast ? 1.5 : 1
            border.color: root.highContrast ? palette.outline : palette.outlineVariant

            Column {
                id: upInner
                x: 18
                y: 18
                width: parent.width - 36
                spacing: 10

                Item {
                    width: parent.width
                    height: 24
                    Row {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8
                        Text {
                            objectName: root.scope + "UpNext"
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Up next"
                            color: palette.inkSurface
                            font.family: M3Font.heading
                            font.pixelSize: M3Font.px(15)
                            font.weight: 600
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(24, upCountLabel.implicitWidth + 14)
                            height: 22
                            radius: 11
                            color: palette.secondaryContainer
                            Text {
                                id: upCountLabel
                                anchors.centerIn: parent
                                text: String(upRows.count)
                                color: palette.inkSecondaryContainer
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(11)
                                font.weight: 600
                            }
                        }
                    }
                }

                Repeater {
                    id: upRows
                    model: root.upModel
                    delegate: rowDelegate
                }

                Item {
                    visible: upRows.count === 0
                    width: parent.width
                    height: Math.max(72, upEmptyText.implicitHeight + 24)
                    Text {
                        id: upEmptyText
                        objectName: root.scope + "UpEmpty"
                        anchors.centerIn: parent
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: "Nothing planned"
                        color: root.muted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                }
            }
        }

        // Done card
        Rectangle {
            id: doneCard
            objectName: root.scope + "DoneCard"
            width: root.cardWidth
            implicitHeight: Math.max(doneInner.implicitHeight + 36, root.balancedMinHeight)
            height: implicitHeight
            radius: palette.cornerFor(16)
            color: palette.cardSurface
            border.width: root.highContrast ? 1.5 : 1
            border.color: root.highContrast ? palette.outline : palette.outlineVariant

            Column {
                id: doneInner
                x: 18
                y: 18
                width: parent.width - 36
                spacing: 10

                Item {
                    width: parent.width
                    height: 24
                    Row {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8
                        Text {
                            objectName: root.scope + "Done"
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Done"
                            color: palette.inkSurface
                            font.family: M3Font.heading
                            font.pixelSize: M3Font.px(15)
                            font.weight: 600
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(24, doneCountLabel.implicitWidth + 14)
                            height: 22
                            radius: 11
                            color: palette.statusDoneTint
                            Text {
                                id: doneCountLabel
                                anchors.centerIn: parent
                                text: String(doneList.count)
                                color: palette.statusDone
                                font.family: M3Font.family
                                font.pixelSize: M3Font.px(11)
                                font.weight: 600
                            }
                        }
                    }
                }

                Repeater {
                    id: doneList
                    model: root.doneModel
                    delegate: rowDelegate
                }

                Item {
                    visible: doneList.count === 0
                    width: parent.width
                    height: Math.max(72, doneEmptyText.implicitHeight + 24)
                    Text {
                        id: doneEmptyText
                        objectName: root.scope + "DoneEmpty"
                        anchors.centerIn: parent
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: "Nothing planned"
                        color: root.muted
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                }
            }
        }
    }

    Component {
        id: rowDelegate
        Item {
            id: line
            required property int index
            required property string title
            required property string subtitle
            required property string icon
            required property string bar
            required property string fill
            required property string ink
            required property string tag
            required property string tagKind
            required property bool canFinish
            required property string assignmentId
            required property bool dim

            width: parent ? parent.width : root.width
            implicitHeight: card.height
            height: implicitHeight
            opacity: line.dim ? 0.68 : 1

            ListRow {
                id: card
                objectName: root.scope + "Row" + line.index
                width: parent.width
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                title: line.title
                subtitle: line.subtitle
                icon: line.icon
                bar: line.bar !== "" ? line.bar : "transparent"
                showBar: line.bar !== ""
                fill: line.fill
                ink: line.ink
                trail: extras.width
                accessName: line.title
                activeFocusOnTab: !root.passive
                onClicked: if (line.assignmentId !== "") root.edit(line.assignmentId)
            }
            Row {
                id: extras
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0
                Tag {
                    objectName: line.tag !== "" ? root.scope + "Tag" + line.index : ""
                    visible: line.tag !== ""
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: line.tagKind !== "" ? line.tagKind : "plain"
                    text: line.tag
                }
                IconButton {
                    objectName: line.canFinish ? root.scope + "Finish" : ""
                    visible: line.canFinish
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "check"
                    ring: root.circle
                    accessName: "Mark " + line.title + " finished"
                    activeFocusOnTab: !root.passive
                    onClicked: root.finish(line.assignmentId)
                }
            }
        }
    }
}
