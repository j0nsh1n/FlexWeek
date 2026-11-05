pragma Singleton
import QtQuick

// Whether focus rings show: true after a key press, false after a mouse or touch press (the host's
// focus_visible filter sets it). It starts true so focus given from code, with no input yet, still shows.
QtObject {
    property bool keyboard: true
}
