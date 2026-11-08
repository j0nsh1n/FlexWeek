import QtQuick
import components 1.0

// A line of words under a field. `problem` draws it in the error colour and announces it.
Text {
    id: root
    property var theme
    property bool problem: false
    M3Palette { id: pal; theme: root.theme }
    visible: text !== ""
    width: parent ? parent.width : implicitWidth
    wrapMode: Text.WordWrap
    color: problem ? pal.error : pal.inkMuted
    font.family: M3Font.family
    font.pixelSize: M3Font.px(12)
    font.weight: 400
    Accessible.role: Accessible.StaticText
    Accessible.name: text
}
