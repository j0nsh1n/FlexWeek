import QtQuick
import components 1.0

SettingsGroup {
    theme: Ui.theme
    density: Ui.density
    reduceMotion: Ui.reduceMotion
    highContrast: Ui.highContrast
    width: parent ? parent.width : 480
}
