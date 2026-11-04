pragma Singleton
import QtQuick

Item {
    visible: false
    FontLoader { id: regular; source: Qt.resolvedUrl("../../../../assets/fonts/RobotoFlex-Regular.ttf") }
    FontLoader { id: medium; source: Qt.resolvedUrl("../../../../assets/fonts/RobotoFlex-Medium.ttf") }
    FontLoader { id: semi; source: Qt.resolvedUrl("../../../../assets/fonts/RobotoFlex-SemiBold.ttf") }
    readonly property string family: regular.name !== "" ? regular.name : "Roboto Flex"
    readonly property bool ready: regular.status === FontLoader.Ready && medium.status === FontLoader.Ready && semi.status === FontLoader.Ready
}
