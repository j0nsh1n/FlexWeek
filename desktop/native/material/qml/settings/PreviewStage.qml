import QtQuick
import components 1.0
import "../views"

// The live preview: the real Material views, drawn from the draft, on a fixed canvas that is scaled to fit
// or shown at actual size. Nothing in it takes input.
Item {
    id: root
    objectName: "previewStage"
    property var settings: Ui.settings
    readonly property var st: Ui.st
    readonly property var draft: settings ? settings.draftTheme : ({})
    readonly property real canvasWidth: 1100
    readonly property real canvasHeight: 700
    readonly property bool fit: Ui.phone || (st.previewFit || "Fit") === "Fit"
    readonly property string shown: st.previewView || "week"
    readonly property real fitScale: Math.min(1, stage.width / canvasWidth, stage.height / canvasHeight)
    readonly property real scaleNow: fit ? Math.max(0.2, fitScale) : 1

    M3Palette { id: palette; theme: Ui.theme }

    Item {
        id: head
        width: parent.width
        height: Ui.phone ? 96 : 56
        Text {
            x: 0
            y: 0
            height: 40
            verticalAlignment: Text.AlignVCenter
            text: "Live preview"
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: 16
            font.weight: 500
        }
        Row {
            anchors.right: parent.right
            y: Ui.phone ? 44 : 0
            spacing: 8
            SegmentedButton {
                objectName: "previewView"
                theme: Ui.theme
                density: Ui.density
                reduceMotion: Ui.reduceMotion
                highContrast: Ui.highContrast
                choices: [{ label: "Week", value: "week" }, { label: "Day", value: "day" }, { label: "Month", value: "month" }]
                current: root.shown
                accessName: "Preview view"
                onSelected: (value) => root.settings.setPreviewView(value)
            }
            SegmentedButton {
                objectName: "previewFit"
                visible: !Ui.phone
                theme: Ui.theme
                density: Ui.density
                reduceMotion: Ui.reduceMotion
                highContrast: Ui.highContrast
                choices: [{ label: "Fit", value: "Fit" }, { label: "Actual size", value: "Actual" }]
                current: st.previewFit || "Fit"
                accessName: "Preview size"
                onSelected: (value) => root.settings.setPreviewFit(value)
            }
        }
    }

    Rectangle {
        id: stage
        objectName: "previewFrame"
        anchors.top: head.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: note.top
        anchors.bottomMargin: 8
        radius: 12
        color: root.draft.surface || palette.surface
        border.width: 1
        border.color: palette.outlineVariant
        clip: true

        Flickable {
            id: scroller
            anchors.fill: parent
            anchors.margins: 1
            contentWidth: root.canvasWidth * root.scaleNow
            contentHeight: root.canvasHeight * root.scaleNow
            interactive: !root.fit
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Item {
                id: canvas
                objectName: "previewCanvas"
                width: root.canvasWidth
                height: root.canvasHeight
                scale: root.scaleNow
                transformOrigin: Item.TopLeft

                Rectangle { anchors.fill: parent; color: root.draft.surface || palette.surface }

                NavRail {
                    id: miniRail
                    height: parent.height
                    theme: root.draft
                    density: st.draftDensity || "comfortable"
                    reduceMotion: true
                    highContrast: st.draftContrast === "high"
                    NavDestination {
                        theme: root.draft; reduceMotion: true; icon: "calendar_view_day"; label: "Day"
                        highContrast: st.draftContrast === "high"
                        selected: root.shown === "day"
                        activeFocusOnTab: false
                    }
                    NavDestination {
                        theme: root.draft; reduceMotion: true; icon: "calendar_view_week"; label: "Week"
                        highContrast: st.draftContrast === "high"
                        selected: root.shown === "week"
                        activeFocusOnTab: false
                    }
                    NavDestination {
                        theme: root.draft; reduceMotion: true; icon: "calendar_month"; label: "Month"
                        highContrast: st.draftContrast === "high"
                        selected: root.shown === "month"
                        activeFocusOnTab: false
                    }
                    NavDestination {
                        theme: root.draft; reduceMotion: true; icon: "task_alt"; label: "My day"
                        highContrast: st.draftContrast === "high"
                        activeFocusOnTab: false
                    }
                    NavDestination {
                        theme: root.draft; reduceMotion: true; icon: "settings"; label: "Settings"; pinned: true
                        highContrast: st.draftContrast === "high"
                        activeFocusOnTab: false
                    }
                }
                Text {
                    x: 100
                    y: 0
                    height: 56
                    verticalAlignment: Text.AlignVCenter
                    text: root.shown === "week" ? "Week" : (root.shown === "day" ? "Day" : "Month")
                    color: root.draft.onSurface || palette.inkSurface
                    font.family: "Roboto Flex"
                    font.pixelSize: 22
                    font.weight: 500
                }
                Item {
                    id: previewViews
                    x: 80
                    y: 56
                    width: root.canvasWidth - 80
                    height: root.canvasHeight - 56
                    clip: true
                    Loader {
                        anchors.fill: parent
                        active: root.shown === "week"
                        sourceComponent: Item {
                            objectName: "settingsPreviewWeek"
                            anchors.fill: parent
                            WeekView {
                                anchors.fill: parent
                                bridge: root.settings.preview
                                theme: root.draft
                                density: st.draftDensity || "comfortable"
                                reduceMotion: true
                                highContrast: st.draftContrast === "high"
                            }
                        }
                    }
                    Loader {
                        anchors.fill: parent
                        active: root.shown === "day"
                        sourceComponent: Item {
                            objectName: "settingsPreviewDay"
                            anchors.fill: parent
                            DayView {
                                anchors.fill: parent
                                bridge: root.settings.preview
                            }
                        }
                    }
                    Loader {
                        anchors.fill: parent
                        active: root.shown === "month"
                        sourceComponent: Item {
                            objectName: "settingsPreviewMonth"
                            anchors.fill: parent
                            MonthView {
                                anchors.fill: parent
                                bridge: root.settings.preview
                                passive: true
                            }
                        }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    z: 100
                    acceptedButtons: Qt.AllButtons
                    onPressed: (mouse) => mouse.accepted = true
                }
                Rectangle {
                    id: statusBanner
                    objectName: "monthPreviewStatus"
                    anchors.top: previewViews.top
                    anchors.topMargin: 8
                    anchors.horizontalCenter: previewViews.horizontalCenter
                    height: 36
                    width: statusRow.width + 24
                    radius: 18
                    M3Palette { id: bannerPalette; theme: root.draft }
                    color: root.settings && root.settings.preview && root.settings.preview.month && root.settings.preview.month.loadError ? bannerPalette.errorContainer : bannerPalette.surfaceContainerHigh
                    visible: root.shown === "month" && root.settings && root.settings.preview && root.settings.preview.month && (root.settings.preview.month.loading || root.settings.preview.month.loadError !== "")
                    z: 150
                    Row {
                        id: statusRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            objectName: "monthPreviewStatusText"
                            text: root.settings && root.settings.preview && root.settings.preview.month && root.settings.preview.month.loading ? "Loading month…" : (root.settings && root.settings.preview && root.settings.preview.month ? root.settings.preview.month.loadError : "")
                            color: root.settings && root.settings.preview && root.settings.preview.month && root.settings.preview.month.loadError ? bannerPalette.inkErrorContainer : bannerPalette.inkSurface
                            font.family: M3Font.family
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Button {
                            objectName: "monthPreviewRetry"
                            text: "Retry"
                            accessName: "Retry loading the month preview"
                            Accessible.name: "Retry loading the month preview"
                            visible: root.settings && root.settings.preview && root.settings.preview.month && !!root.settings.preview.month.loadError
                            kind: "text"
                            height: 28
                            implicitHeight: 28
                            anchors.verticalCenter: parent.verticalCenter
                            theme: root.draft
                            activeFocusOnTab: true
                            onClicked: if (root.settings && root.settings.preview && root.settings.preview.month) root.settings.preview.month.retry()
                        }
                    }
                }
            }
        }
    }
    Text {
        id: note
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 20
        text: "The real Material views, drawn from these values. Nothing else changes until Done."
        color: palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: 12
        elide: Text.ElideRight
    }
}
