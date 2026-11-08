pragma Singleton
import QtQuick

Item {
    visible: false
    FontLoader { id: regular; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Regular.ttf") }
    FontLoader { id: medium; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Medium.ttf") }
    FontLoader { id: semi; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-SemiBold.ttf") }
    readonly property string family: regular.name !== "" ? regular.name : "Inter"
    // The student's text size (Small to Larger). Main sets it from the theme; every Text sizes through px().
    // `most` caps text that sits in a fixed slot, such as a rail label.
    property real scale: 1
    function px(size, most) {
        var grown = Math.round(size * scale)
        return most === undefined ? grown : Math.min(grown, most)
    }
    readonly property bool ready: regular.status === FontLoader.Ready && medium.status === FontLoader.Ready && semi.status === FontLoader.Ready
}
