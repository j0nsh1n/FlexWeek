import QtQuick
import components 1.0

// An outlined text field that follows `wanted`: what the bridge holds. It is cleared when the bridge
// clears it, and left alone while the two already agree, so the cursor does not jump while typing.
OutlinedField {
    id: field
    property string wanted: ""
    onWantedChanged: if (text !== wanted) text = wanted
    Component.onCompleted: text = wanted
}
