pragma Singleton
import QtQuick

// The one place the Animations level and Motion speed reach the QML. The shell binds `pace` and `reach` from the
// bridge (see native/motion_level.py): pace stretches every duration, 0 being at once; reach stretches every
// distance, 0 being fades only. Every animation asks `fade` (colour, opacity) or `travel` (position, size, scale).
QtObject {
    property real pace: 1
    property real reach: 1

    // A control's own `reduceMotion` is "no travel". In the app that is the same as reach 0, and fades stay (Reduce).
    // A control set still on its own (the Look preview, a gallery) also stops fading while the app's level moves.
    function fade(ms, still) {
        if (still && reach > 0)
            return 0
        return Math.round(ms * pace)
    }

    function travel(ms, still) {
        if (still || reach <= 0)
            return 0
        return Math.round(ms * pace)
    }
}
