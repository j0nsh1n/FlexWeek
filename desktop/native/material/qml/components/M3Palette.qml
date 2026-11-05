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
    readonly property color statusDone: tone("statusDone", "#2f7d4a")
    readonly property color statusDueSoon: tone("statusDueSoon", "#8a5a00")
    readonly property color statusOverdue: tone("statusOverdue", "#b42318")
    readonly property color statusDoneTint: tone("statusDoneTint", "#deeae2")
    readonly property color statusDueSoonTint: tone("statusDueSoonTint", "#ece5d6")
    readonly property color statusOverdueTint: tone("statusOverdueTint", "#f3dcda")
    readonly property var classes: (theme && theme.classes) ? theme.classes : ({})

    readonly property color disabledFill: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.12)
    readonly property color disabledInk: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.38)
    readonly property real stroke: 1
}
