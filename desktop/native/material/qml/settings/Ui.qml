pragma Singleton
import QtQuick

// What every settings control reads. SettingsView fills it in; controls never reach for the app.
QtObject {
    property var bridge: null
    property var settings: null
    property var theme: ({})
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    readonly property var st: settings ? settings.state : ({})
}
