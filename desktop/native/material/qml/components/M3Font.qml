pragma Singleton
import QtQuick

Item {
    visible: false
    FontLoader { id: regular; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Regular.ttf") }
    FontLoader { id: medium; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-Medium.ttf") }
    FontLoader { id: semi; source: Qt.resolvedUrl("../../../../assets/fonts/Inter-SemiBold.ttf") }
    FontLoader { id: newsreader; source: Qt.resolvedUrl("../../../../assets/fonts/Newsreader-Medium.ttf") }
    FontLoader { id: newsreaderRegular; source: Qt.resolvedUrl("../../../../assets/fonts/Newsreader-Regular.ttf") }
    FontLoader { id: newsreaderSemi; source: Qt.resolvedUrl("../../../../assets/fonts/Newsreader-SemiBold.ttf") }
    FontLoader { id: mono; source: Qt.resolvedUrl("../../../../assets/fonts/JetBrainsMono-Medium.ttf") }
    FontLoader { id: monoRegular; source: Qt.resolvedUrl("../../../../assets/fonts/JetBrainsMono-Regular.ttf") }
    FontLoader { id: monoSemi; source: Qt.resolvedUrl("../../../../assets/fonts/JetBrainsMono-SemiBold.ttf") }
    // The student's font (Sans, Serif or Mono) as the faces it names. Main sets these from the theme.
    property string bodyName: "Inter"
    property string headingName: "Inter"
    function face(name) {
        if (name === "Newsreader")
            return newsreader.name !== "" ? newsreader.name : "Newsreader"
        if (name === "JetBrains Mono")
            return mono.name !== "" ? mono.name : "JetBrains Mono"
        return regular.name !== "" ? regular.name : "Inter"
    }
    readonly property string family: face(bodyName)
    // The bundled mono face for codes and timers: one loaded family name, never a fallback list.
    readonly property string monoFamily: face("JetBrains Mono")
    // Titles and group titles. Serif is Newsreader here over Inter everywhere else.
    readonly property string heading: face(headingName)
    // The student's text size (Small to Larger). Main sets it from the theme; every Text sizes through px().
    // `most` caps text that sits in a fixed slot, such as a rail label.
    property real scale: 1
    function px(size, most) {
        var grown = Math.round(size * scale)
        return most === undefined ? grown : Math.min(grown, most)
    }
    readonly property bool ready: regular.status === FontLoader.Ready && medium.status === FontLoader.Ready && semi.status === FontLoader.Ready
}
