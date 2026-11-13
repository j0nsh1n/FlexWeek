pragma Singleton
import QtQuick

// The day weeks start on, 0 Monday to 6 Sunday, kept on this computer. Main sets it from the bridge; a
// small month starts its rows on it.
QtObject {
    property int firstDay: 0
}
