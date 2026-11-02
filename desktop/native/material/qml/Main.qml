import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Item {
    id: root
    objectName: "materialShell"
    // Set before the shell is created. A context property was null by the time these bindings ran.
    property var bridge
    Material.theme: bridge.dark ? Material.Dark : Material.Light
    Material.primary: bridge.primary
    Material.accent: bridge.primary
    Material.background: bridge.surface
    Material.foreground: bridge.onSurface

    Rectangle {
        anchors.fill: parent
        color: bridge.surface
    }

    // An 80-wide rail cannot use a Material button's default padding: "Week" vanishes and
    // "Settings" collapses to an ellipsis.
    component RailButton: Button {
        padding: 2
        leftPadding: 2
        rightPadding: 2
        topPadding: 8
        bottomPadding: 8
        font.pixelSize: 12
        font.capitalization: Font.MixedCase
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: rail
            objectName: "materialRail"
            Layout.preferredWidth: 80
            Layout.minimumWidth: 80
            Layout.maximumWidth: 80
            Layout.fillHeight: true
            color: bridge.surfaceContainer
            border.width: bridge.stroke
            border.color: bridge.outline
            clip: true

            Column {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 12
                spacing: 8

                Rectangle {
                    objectName: "materialFab"
                    width: 56
                    height: 56
                    radius: 16
                    color: bridge.primary
                    anchors.horizontalCenter: parent.horizontalCenter

                    Label {
                        anchors.centerIn: parent
                        text: "+"
                        color: bridge.onPrimary
                        font.pixelSize: 28
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: bridge.addHomework()
                    }
                }

                RailButton {
                    objectName: "navWeek"
                    text: "Week"
                    width: parent.width
                    checkable: true
                    checked: bridge.pageIndex === 0
                    onClicked: bridge.showWeek()
                }

                RailButton {
                    objectName: "navDay"
                    text: "Day"
                    visible: bridge.later
                    width: parent.width
                    onClicked: bridge.showPage("day")
                }

                RailButton {
                    objectName: "navMonth"
                    text: "Month"
                    visible: bridge.later
                    width: parent.width
                    onClicked: bridge.showPage("month")
                }

                RailButton {
                    objectName: "navMyDay"
                    text: "My day"
                    visible: bridge.later
                    width: parent.width
                    onClicked: bridge.showPage("myday")
                }
            }

            RailButton {
                objectName: "navSettings"
                text: "Settings"
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 8
                checkable: true
                checked: bridge.pageIndex === 1
                onClicked: bridge.showSettings()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                objectName: "materialTop"
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                color: bridge.surface

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 12
                    spacing: 8

                    Label {
                        objectName: "materialTitle"
                        text: bridge.title
                        color: bridge.onSurface
                        font.pixelSize: 22
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Label {
                        objectName: "materialClock"
                        text: bridge.clockText
                        color: bridge.onSurface
                        font.pixelSize: 16
                    }

                    Button {
                        objectName: "materialUndo"
                        text: "Undo"
                        enabled: bridge.canUndo
                        onClicked: bridge.undo()
                    }

                    Button {
                        objectName: "materialRedo"
                        text: "Redo"
                        enabled: bridge.canRedo
                        onClicked: bridge.redo()
                    }

                    Button {
                        objectName: "materialMore"
                        text: "More"
                        onClicked: bridge.openMore()
                    }
                }
            }

            StackLayout {
                objectName: "materialPages"
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: bridge.pageIndex

                Item {
                    id: weekPane
                    objectName: "materialWeek"
                    property real dayWidth: Math.max(48, (width - 64) / 7)

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        Row {
                            Layout.fillWidth: true
                            Layout.leftMargin: 64
                            Layout.preferredHeight: 36
                            spacing: 0

                            Repeater {
                                id: dayHeaders
                                objectName: "dayHeaders"
                                model: bridge.days

                                Label {
                                    objectName: "dayHeader"
                                    text: model.label
                                    width: weekPane.dayWidth
                                    height: 36
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    color: bridge.onSurface
                                }
                            }
                        }

                        Flickable {
                            id: scroller
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            contentWidth: width
                            contentHeight: 24 * bridge.hourRow
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            // Keep the now line on screen, and the earliest block with it when both fit.
                            function revealNow() {
                                var view = height
                                if (view < 40 || bridge.nowDay < 0)
                                    return
                                var row = bridge.hourRow
                                var nowY = bridge.nowMinute / 60 * row
                                var earliest = nowY
                                var rows = bridge.blockRows
                                for (var i = 0; i < rows.length; i++) {
                                    var top = rows[i].start / 60 * row
                                    if (top < earliest)
                                        earliest = top
                                }
                                var contentY = (nowY - earliest + 48 < view)
                                        ? Math.max(0, earliest - 24)
                                        : Math.max(0, nowY - view * 0.65)
                                var limit = Math.max(0, contentHeight - view)
                                scroller.contentY = Math.min(Math.max(0, contentY), limit)
                            }

                            onHeightChanged: revealNow()

                            Connections {
                                target: bridge
                                function onBlocksChanged() { scroller.revealNow() }
                                function onChanged() { scroller.revealNow() }
                            }

                            Item {
                                width: scroller.width
                                height: 24 * bridge.hourRow

                                Repeater {
                                    model: 24

                                    Rectangle {
                                        y: index * bridge.hourRow
                                        width: parent.width
                                        height: 1
                                        color: bridge.outlineVariant
                                    }
                                }

                                Repeater {
                                    id: hourLabels
                                    objectName: "hourLabels"
                                    model: bridge.hours

                                    Label {
                                        objectName: "hourLabel"
                                        x: 4
                                        y: index * bridge.hourRow + 2
                                        width: 56
                                        text: model.label
                                        color: bridge.onSurface
                                        font.pixelSize: 11
                                    }
                                }

                                Repeater {
                                    id: weekBlocks
                                    objectName: "weekBlocks"
                                    model: bridge.blocks

                                    Rectangle {
                                        objectName: "weekBlock"
                                        x: 64 + model.day * weekPane.dayWidth + 3
                                        y: model.start / 60 * bridge.hourRow
                                        width: Math.max(8, weekPane.dayWidth - 8)
                                        height: Math.max(36, (model.end - model.start) / 60 * bridge.hourRow - 2)
                                        radius: 12
                                        color: model.fill
                                        border.width: bridge.stroke
                                        border.color: bridge.outline

                                        Label {
                                            objectName: "weekBlockTitle"
                                            text: model.title
                                            color: model.ink
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            anchors.topMargin: 6
                                            anchors.bottomMargin: 6
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }
                                    }
                                }

                                Rectangle {
                                    objectName: "nowLine"
                                    visible: bridge.nowDay >= 0
                                    x: 64
                                    y: bridge.nowMinute / 60 * bridge.hourRow
                                    width: parent.width - 64
                                    height: Math.max(2, bridge.stroke)
                                    color: bridge.primary
                                    z: 3
                                }
                            }
                        }

                        Rectangle {
                            objectName: "homeworkDrawer"
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(168, 36 + Math.max(bridge.homeworkCount, 1) * 22)
                            color: bridge.surfaceContainer

                            Column {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 2

                                Label {
                                    objectName: "homeworkCount"
                                    text: bridge.homeworkCount === 1
                                          ? "1 still needs a time"
                                          : bridge.homeworkCount + " still need a time"
                                    color: bridge.onSurface
                                }

                                Repeater {
                                    id: homeworkRows
                                    objectName: "homeworkRows"
                                    model: bridge.homework

                                    Label {
                                        objectName: "homeworkTitle"
                                        text: model.title
                                        color: bridge.onSurface
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    objectName: "materialSettings"

                    Column {
                        anchors.centerIn: parent
                        spacing: 16
                        width: 360

                        Label {
                            text: "Material 3"
                            color: bridge.onSurface
                            font.pixelSize: 22
                        }

                        Label {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: "The week is the same data as the other styles."
                            color: bridge.onSurface
                        }

                        Button {
                            objectName: "useWidgets"
                            text: "Widgets styles"
                            onClicked: bridge.useWidgets()
                        }
                    }
                }

                Item {
                    Label {
                        anchors.centerIn: parent
                        visible: bridge.later
                        text: "Day comes in a later slice."
                        color: bridge.onSurface
                    }
                }

                Item {
                    Label {
                        anchors.centerIn: parent
                        visible: bridge.later
                        text: "Month comes in a later slice."
                        color: bridge.onSurface
                    }
                }

                Item {
                    Label {
                        anchors.centerIn: parent
                        visible: bridge.later
                        text: "My day comes in a later slice."
                        color: bridge.onSurface
                    }
                }
            }
        }
    }
}
