import QtQuick
import components 1.0

Column {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string scope: "day"
    property var upModel
    property var doneModel
    signal finish(string assignmentId)
    signal edit(string assignmentId)

    width: parent ? parent.width : implicitWidth
    spacing: 8

    M3Palette { id: palette; theme: root.theme }
    readonly property color muted: palette.inkMuted

    Text {
        objectName: root.scope + "UpNext"
        text: "Up next"
        color: root.muted
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    Repeater {
        id: upRows
        model: root.upModel
        delegate: rowDelegate
    }
    Text {
        objectName: root.scope + "UpEmpty"
        visible: upRows.count === 0
        text: "Nothing planned"
        color: root.muted
        font.family: M3Font.family
        font.pixelSize: 14
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    Text {
        objectName: root.scope + "Done"
        text: "Done"
        color: root.muted
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    Repeater {
        id: doneList
        model: root.doneModel
        delegate: rowDelegate
    }
    Text {
        objectName: root.scope + "DoneEmpty"
        visible: doneList.count === 0
        text: "Nothing planned"
        color: root.muted
        font.family: M3Font.family
        font.pixelSize: 14
        Accessible.role: Accessible.StaticText
        Accessible.name: text
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

            width: root.width
            implicitHeight: card.height
            height: implicitHeight
            opacity: line.dim ? 0.65 : 1

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
                    accessName: "Mark " + line.title + " finished"
                    onClicked: root.finish(line.assignmentId)
                }
            }
        }
    }
}
