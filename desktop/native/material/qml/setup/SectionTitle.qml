import QtQuick
import components 1.0

Text {
    id: root
    property var theme
    M3Palette { id: palette; theme: root.theme }
    color: palette.inkSurface
    font.family: M3Font.family
    font.pixelSize: M3Font.px(16)
    font.weight: 500
    wrapMode: Text.WordWrap
    topPadding: 8
    Accessible.role: Accessible.Heading
    Accessible.name: text
}
