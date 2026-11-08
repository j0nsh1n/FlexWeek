import QtQuick
import components 1.0

Text {
    id: root
    property var theme
    M3Palette { id: palette; theme: root.theme }
    color: palette.inkMuted
    font.family: M3Font.family
    font.pixelSize: M3Font.px(14)
    wrapMode: Text.WordWrap
}
