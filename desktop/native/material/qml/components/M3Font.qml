pragma Singleton
import QtQuick

Item {
    visible: false
    FontLoader { id: regular; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Regular.ttf") }
    FontLoader { id: medium; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Medium.ttf") }
    FontLoader { id: semi; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-SemiBold.ttf") }
    readonly property string family: regular.name !== "" ? regular.name : "Inter"
    readonly property bool ready: regular.status === FontLoader.Ready && medium.status === FontLoader.Ready && semi.status === FontLoader.Ready
}
