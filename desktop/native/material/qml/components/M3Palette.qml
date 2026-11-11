import QtQuick

// Resolves one theme object (camelCase Material roles) into colours, with the
// Slate light scheme as the stand-in when a role is missing.
QtObject {
    id: palette
    property var theme

    function tone(name, fallback) {
        if (theme == null)
            return fallback
        var value = theme[name]
        if (value == null || value === "")
            return fallback
        return value
    }

    // Names do not start with "on": QML treats that prefix as a signal handler.
    readonly property color primary: tone("primary", "#3d6fc4")
    readonly property color inkPrimary: tone("onPrimary", "#ffffff")
    readonly property color primaryContainer: tone("primaryContainer", "#d7e2ff")
    readonly property color inkPrimaryContainer: tone("onPrimaryContainer", "#294677")
    readonly property color secondary: tone("secondary", "#565e71")
    readonly property color inkSecondary: tone("onSecondary", "#ffffff")
    readonly property color secondaryContainer: tone("secondaryContainer", "#e6edf8")
    readonly property color inkSecondaryContainer: tone("onSecondaryContainer", "#0f172a")
    readonly property color tertiary: tone("tertiary", "#705574")
    readonly property color inkTertiary: tone("onTertiary", "#ffffff")
    readonly property color tertiaryContainer: tone("tertiaryContainer", "#fad8fd")
    readonly property color inkTertiaryContainer: tone("onTertiaryContainer", "#573e5c")
    readonly property color error: tone("error", "#ba1a1a")
    readonly property color inkError: tone("onError", "#ffffff")
    readonly property color errorContainer: tone("errorContainer", "#ffdad6")
    readonly property color inkErrorContainer: tone("onErrorContainer", "#93000a")
    readonly property color surface: tone("surface", "#eef1f5")
    readonly property color inkSurface: tone("onSurface", "#0f172a")
    readonly property color inkMuted: tone("onSurfaceVariant", "#475569")
    readonly property color surfaceContainerLowest: tone("surfaceContainerLowest", "#ffffff")
    readonly property color surfaceContainerLow: tone("surfaceContainerLow", "#ffffff")
    readonly property color surfaceContainer: tone("surfaceContainer", "#ffffff")
    readonly property color surfaceContainerHigh: tone("surfaceContainerHigh", "#ffffff")
    readonly property color surfaceContainerHighest: tone("surfaceContainerHighest", "#ffffff")
    readonly property color surfaceVariant: tone("surfaceVariant", "#ffffff")
    readonly property color outline: tone("outline", "#64748b")
    readonly property color outlineVariant: tone("outlineVariant", "#e5e9f0")
    readonly property color inverseSurface: tone("inverseSurface", "#2e3036")
    readonly property color inverseOnSurface: tone("inverseOnSurface", "#f0f0f7")
    readonly property color inversePrimary: tone("inversePrimary", "#abc7ff")

    // Theme object keys (B3a3)
    readonly property color page: tone("page", "#eef1f5")
    readonly property color card: tone("card", "#ffffff")
    readonly property color edge: tone("edge", "#e5e9f0")
    readonly property color focusRing: tone("focusRing", "#3d6fc4")
    // Status colours: dark from spec; light values proposed, not in the spec
    readonly property color statusDone: tone("statusDone", "#276b3f")
    readonly property color statusDueSoon: tone("statusDueSoon", "#8a5a00")
    readonly property color statusOverdue: tone("statusOverdue", "#b42318")
    readonly property color statusDoneTint: tone("statusDoneTint", "#deeae2")
    readonly property color statusDueSoonTint: tone("statusDueSoonTint", "#ece5d6")
    readonly property color statusOverdueTint: tone("statusOverdueTint", "#f3dcda")
    readonly property var classes: (theme && theme.classes) ? theme.classes : ({})

    readonly property bool dark: surface.r * 0.2126 + surface.g * 0.7152 + surface.b * 0.0722 < 0.4

    // What a block of each kind falls back to when the theme carries no `classes`.
    readonly property var defaultClasses: ({
        "class": {
            bar: "#3d6fc4",
            fill: dark ? "#1e2c44" : "#e4ebf7",
            ink: dark ? "#ececec" : "#0f172a"
        },
        "exercise": {
            bar: "#2b9665",
            fill: dark ? "#1a352e" : "#e1f0e9",
            ink: dark ? "#ececec" : "#0f172a"
        },
        "extra": {
            bar: "#0f8a8a",
            fill: dark ? "#133336" : "#ddefef",
            ink: dark ? "#ececec" : "#0f172a"
        },
        "assignments": {
            bar: "#a87512",
            fill: dark ? "#382e1a" : "#f3ecde",
            ink: dark ? "#ececec" : "#0f172a"
        },
        "study": {
            bar: "#c2557a",
            fill: dark ? "#3e2633" : "#f6e7ec",
            ink: dark ? "#ececec" : "#0f172a"
        },
        "other": {
            bar: "#64748b",
            fill: dark ? "#272d37" : "#e9ecef",
            ink: dark ? "#ececec" : "#0f172a"
        }
    })

    // The bar, fill and ink of a category: the one source for a block's colours in Week and Day and
    // for a Month entry's strip.
    function classFor(category) {
        var cls = classes
        var key = category
        if (key === "school") key = "class"
        else if (key === "sports") key = "exercise"
        else if (key === "homework") key = "assignments"
        else if (key === "clubs") key = "extra"
        if (cls && cls[key])
            return cls[key]
        if (cls && cls["other"])
            return cls["other"]
        if (defaultClasses[key])
            return defaultClasses[key]
        return defaultClasses["other"]
    }

    readonly property color disabledFill: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.12)
    readonly property color disabledInk: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.38)
    readonly property real stroke: 1
}
