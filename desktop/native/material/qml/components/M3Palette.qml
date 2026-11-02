import QtQuick

// Resolves one theme object (camelCase Material roles) into colours, with the
// Blue light scheme as the stand-in when a role is missing.
QtObject {
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
    readonly property color primary: tone("primary", "#425e91")
    readonly property color inkPrimary: tone("onPrimary", "#ffffff")
    readonly property color primaryContainer: tone("primaryContainer", "#d7e2ff")
    readonly property color inkPrimaryContainer: tone("onPrimaryContainer", "#294677")
    readonly property color secondary: tone("secondary", "#565e71")
    readonly property color inkSecondary: tone("onSecondary", "#ffffff")
    readonly property color secondaryContainer: tone("secondaryContainer", "#dae2f9")
    readonly property color inkSecondaryContainer: tone("onSecondaryContainer", "#3e4759")
    readonly property color tertiary: tone("tertiary", "#705574")
    readonly property color inkTertiary: tone("onTertiary", "#ffffff")
    readonly property color tertiaryContainer: tone("tertiaryContainer", "#fad8fd")
    readonly property color inkTertiaryContainer: tone("onTertiaryContainer", "#573e5c")
    readonly property color error: tone("error", "#ba1a1a")
    readonly property color inkError: tone("onError", "#ffffff")
    readonly property color errorContainer: tone("errorContainer", "#ffdad6")
    readonly property color inkErrorContainer: tone("onErrorContainer", "#93000a")
    readonly property color surface: tone("surface", "#f9f9ff")
    readonly property color inkSurface: tone("onSurface", "#1a1c20")
    readonly property color inkMuted: tone("onSurfaceVariant", "#44474e")
    readonly property color surfaceContainerLowest: tone("surfaceContainerLowest", "#ffffff")
    readonly property color surfaceContainerLow: tone("surfaceContainerLow", "#f3f3fa")
    readonly property color surfaceContainer: tone("surfaceContainer", "#ededf4")
    readonly property color surfaceContainerHigh: tone("surfaceContainerHigh", "#e8e7ee")
    readonly property color surfaceContainerHighest: tone("surfaceContainerHighest", "#e2e2e9")
    readonly property color surfaceVariant: tone("surfaceVariant", "#e0e2ec")
    readonly property color outline: tone("outline", "#74777f")
    readonly property color outlineVariant: tone("outlineVariant", "#c4c6d0")
    readonly property color inverseSurface: tone("inverseSurface", "#2e3036")
    readonly property color inverseOnSurface: tone("inverseOnSurface", "#f0f0f7")
    readonly property color inversePrimary: tone("inversePrimary", "#abc7ff")

    readonly property color disabledFill: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.12)
    readonly property color disabledInk: Qt.rgba(inkSurface.r, inkSurface.g, inkSurface.b, 0.38)
    readonly property real stroke: 1
}
