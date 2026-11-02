import QtQuick
import components 1.0

Flickable {
    id: page
    default property alias content: column.data
    property int maxWidth: 720
    readonly property int pad: Ui.phone ? 16 : 24

    contentWidth: width
    contentHeight: column.implicitHeight + 36
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick

    Column {
        id: column
        x: page.pad
        y: 12
        width: Math.max(0, Math.min(page.maxWidth, page.width - page.pad * 2))
        spacing: 12
    }
    Rectangle {
        objectName: "scrollIndicator"
        visible: page.contentHeight > page.height + 1
        x: page.width - 6
        width: 4
        radius: 2
        y: page.height * (page.contentY / Math.max(1, page.contentHeight))
        height: Math.max(24, page.height * page.height / Math.max(1, page.contentHeight))
        color: Ui.theme.outline || "#74777f"
        opacity: 0.5
    }
}
