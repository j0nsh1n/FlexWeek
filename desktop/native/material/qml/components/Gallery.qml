import QtQuick

Rectangle {
    id: root
    objectName: "gallery"
    property string scheme: "light"
    property string density: "comfortable"
    property bool reduceMotion: false
    readonly property bool highContrast: scheme === "high"
    readonly property var theme: scheme === "dark" ? darkTheme : scheme === "high" ? highTheme : lightTheme

    property var lightTheme: ({
        "primary": "#425e91", "onPrimary": "#ffffff", "primaryContainer": "#d7e2ff", "onPrimaryContainer": "#294677",
        "secondary": "#565e71", "onSecondary": "#ffffff", "secondaryContainer": "#dae2f9", "onSecondaryContainer": "#3e4759",
        "tertiary": "#705574", "onTertiary": "#ffffff", "tertiaryContainer": "#fad8fd", "onTertiaryContainer": "#573e5c",
        "error": "#ba1a1a", "onError": "#ffffff", "errorContainer": "#ffdad6", "onErrorContainer": "#93000a",
        "surface": "#f9f9ff", "onSurface": "#1a1c20", "onSurfaceVariant": "#44474e",
        "surfaceContainerLowest": "#ffffff", "surfaceContainerLow": "#f3f3fa", "surfaceContainer": "#ededf4",
        "surfaceContainerHigh": "#e8e7ee", "surfaceContainerHighest": "#e2e2e9", "surfaceVariant": "#e0e2ec",
        "outline": "#74777f", "outlineVariant": "#c4c6d0",
        "inverseSurface": "#2e3036", "inverseOnSurface": "#f0f0f7", "inversePrimary": "#abc7ff"
    })
    property var darkTheme: ({
        "primary": "#abc7ff", "onPrimary": "#0c305f", "primaryContainer": "#294677", "onPrimaryContainer": "#d7e2ff",
        "secondary": "#bec6dc", "onSecondary": "#283041", "secondaryContainer": "#3e4759", "onSecondaryContainer": "#dae2f9",
        "tertiary": "#ddbce0", "onTertiary": "#3f2844", "tertiaryContainer": "#573e5c", "onTertiaryContainer": "#fad8fd",
        "error": "#ffb4ab", "onError": "#690005", "errorContainer": "#93000a", "onErrorContainer": "#ffdad6",
        "surface": "#111318", "onSurface": "#e2e2e9", "onSurfaceVariant": "#c4c6d0",
        "surfaceContainerLowest": "#0c0e13", "surfaceContainerLow": "#1a1c20", "surfaceContainer": "#1e2025",
        "surfaceContainerHigh": "#282a2f", "surfaceContainerHighest": "#33353a", "surfaceVariant": "#44474e",
        "outline": "#8e9099", "outlineVariant": "#44474e",
        "inverseSurface": "#e2e2e9", "inverseOnSurface": "#2e3036", "inversePrimary": "#425e91"
    })
    property var highTheme: ({
        "primary": "#052b5b", "onPrimary": "#ffffff", "primaryContainer": "#2b497a", "onPrimaryContainer": "#ffffff",
        "secondary": "#242c3d", "onSecondary": "#ffffff", "secondaryContainer": "#41495b", "onSecondaryContainer": "#ffffff",
        "tertiary": "#3b2440", "onTertiary": "#ffffff", "tertiaryContainer": "#5a405e", "onTertiaryContainer": "#ffffff",
        "error": "#600004", "onError": "#ffffff", "errorContainer": "#98000a", "onErrorContainer": "#ffffff",
        "surface": "#f9f9ff", "onSurface": "#000000", "onSurfaceVariant": "#000000",
        "surfaceContainerLowest": "#ffffff", "surfaceContainerLow": "#f0f0f7", "surfaceContainer": "#e2e2e9",
        "surfaceContainerHigh": "#d4d4db", "surfaceContainerHighest": "#c6c6cd", "surfaceVariant": "#e0e2ec",
        "outline": "#292c33", "outlineVariant": "#464951",
        "inverseSurface": "#2e3036", "inverseOnSurface": "#ffffff", "inversePrimary": "#abc7ff"
    })

    color: theme.surface
    width: 1080
    height: page.implicitHeight + 32

    Column {
        id: page
        x: 16
        y: 16
        width: parent.width - 32
        spacing: 20

        Text {
            text: "Material 3 components"
            color: root.theme.onSurface
            font.family: M3Font.family
            font.pixelSize: 24
            font.weight: 400
        }

        Row {
            spacing: 16
            NavRail {
                objectName: "railMeasure"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                height: 420
                Fab {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    accessName: "Add"
                }
                NavDestination {
                    objectName: "destMeasure"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "calendar_view_week"
                    label: "Week"
                    selected: true
                }
                NavDestination {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "calendar_view_day"
                    label: "Day"
                }
                NavDestination {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "calendar_month"
                    label: "Month"
                }
                NavDestination {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "wb_sunny"
                    label: "My day"
                }
                NavDestination {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    icon: "settings"
                    label: "Settings"
                    pinned: true
                }
            }
            Column {
                spacing: 12
                NavBar {
                    objectName: "barMeasure"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    width: 480
                    NavDestination {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "calendar_view_day"
                        label: "Day"
                    }
                    NavDestination {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "calendar_view_week"
                        label: "Week"
                        selected: true
                    }
                    NavDestination {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "wb_sunny"
                        label: "My day"
                    }
                    NavDestination {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        icon: "settings"
                        label: "Settings"
                    }
                }
                Row {
                    spacing: 12
                    Fab {
                        objectName: "fabMeasure"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                    }
                    Fab {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        enabled: false
                        accessName: "Add, unavailable"
                    }
                    ExtendedFab {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        text: "Add homework"
                    }
                }
                Flow {
                    width: 720
                    spacing: 8
                    Button { objectName: "filledMeasure"; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "filled"; text: "Save" }
                    Button { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "tonal"; text: "Done" }
                    Button { objectName: "outlinedMeasure"; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "outlined"; text: "Outline" }
                    Button { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "text"; text: "Cancel" }
                    Button { objectName: "disabledMeasure"; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "filled"; text: "Save"; enabled: false }
                    Button { objectName: "textDisabledMeasure"; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "text"; text: "Cancel"; enabled: false }
                    Button { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "outlined"; text: "Outline"; enabled: false }
                    Button { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; kind: "tonal"; text: "Done"; enabled: false }
                    IconButton { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; icon: "more_vert"; accessName: "More" }
                    IconButton { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; icon: "close"; accessName: "Close"; enabled: false }
                    IconButton { theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; icon: "edit_note"; accessName: "Edit"; small: true }
                }
                SegmentedButton {
                    objectName: "segmentMeasure"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    accessName: "Density"
                    current: "comfortable"
                    choices: [
                        { "label": "Comfortable", "value": "comfortable" },
                        { "label": "Compact", "value": "compact" }
                    ]
                }
                Row {
                    spacing: 16
                    Switch {
                        objectName: "switchMeasure"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        accessName: "Weekends"
                        checked: false
                    }
                    Switch {
                        objectName: "switchOn"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        accessName: "Weekends on"
                        checked: true
                    }
                    Switch {
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        accessName: "Weekends unavailable"
                        enabled: false
                    }
                }
            }
        }

        Row {
            spacing: 8
            PresetSwatch {
                objectName: "swatchMeasure"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Blue"
                selected: true
                accessName: "Blue"
                quadrantPrimary: "#425e91"
                quadrantTertiary: "#705574"
                quadrantSecondary: "#dae2f9"
                quadrantPrimaryContainer: "#d7e2ff"
            }
            PresetSwatch {
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: "Sea"
                accessName: "Sea"
                quadrantPrimary: "#00696e"
                quadrantTertiary: "#4e5f7d"
                quadrantSecondary: "#cce8e9"
                quadrantPrimaryContainer: "#9cf0f6"
            }
        }

        SettingsGroup {
            objectName: "groupMeasure"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            width: 560
            SettingsRow {
                objectName: "rowMeasure"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                title: "Weekends"
                subtitle: "Show Saturday and Sunday"
                Switch {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    checked: true
                    accessName: "Show weekends"
                }
            }
            SettingsRow {
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                title: "Density"
                subtitle: "How much fits on the screen"
                SegmentedButton {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    current: "comfortable"
                    choices: [
                        { "label": "Comfortable", "value": "comfortable" },
                        { "label": "Compact", "value": "compact" }
                    ]
                }
            }
        }

        SettingsGroup {
            theme: root.theme
            density: "compact"
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            width: 560
            SettingsRow {
                objectName: "compactRow"
                theme: root.theme
                title: "Hour row"
                subtitle: "Shorter rows"
            }
        }

        Column {
            spacing: 8
            width: 560
            ListRow {
                width: 560
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                icon: "school"
                title: "History essay"
                subtitle: "Due Thursday"
                showBar: true
                bar: "#c98a2b"
            }
            ListRow {
                width: 560
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                title: "No icon"
                subtitle: "Still a row"
            }
        }

        Row {
            spacing: 8
            Tag { theme: root.theme; highContrast: root.highContrast; text: "Plain" }
            Tag { theme: root.theme; highContrast: root.highContrast; kind: "tight"; text: "Tight" }
            Tag { theme: root.theme; highContrast: root.highContrast; kind: "plenty"; text: "Plenty" }
            Tag { theme: root.theme; highContrast: root.highContrast; kind: "cutting"; text: "Cutting" }
        }

        Row {
            spacing: 8
            EventBlock {
                objectName: "eventMeasure"
                width: 160
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                category: "school"
                title: "History essay on the Tudor succession"
                detail: "16:00"
            }
            EventBlock {
                width: 140
                theme: root.theme
                highContrast: root.highContrast
                category: "sports"
                title: "Soccer"
                detail: "15:30"
            }
            EventBlock {
                width: 140
                theme: root.theme
                highContrast: root.highContrast
                category: "study"
                title: "Bio reading"
                detail: "18:00"
            }
            EventBlock {
                width: 140
                theme: root.theme
                highContrast: root.highContrast
                category: "homework"
                title: "Maths set"
                detail: "19:00"
            }
            EventBlock {
                objectName: "pastEvent"
                width: 140
                theme: root.theme
                highContrast: root.highContrast
                category: "school"
                title: "Registration"
                detail: "09:00"
                past: true
            }
        }

        OutlinedField {
            objectName: "fieldMeasure"
            width: 320
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            label: "Title"
            placeholder: "History essay"
        }

        Row {
            spacing: 16
            Item {
                objectName: "dialogHost"
                width: 472
                height: 260
                Dialog {
                    objectName: "dialogMeasure"
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    open: true
                    title: "Move the history essay?"
                    body: "It overlaps soccer. Move it to 19:00."
                    confirmText: "Move"
                    dismissText: "Cancel"
                }
            }
            Item {
                width: 270
                height: 260
                BottomSheet {
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    open: true
                    title: "More"
                    body: "Undo, redo, and the week."
                }
            }
            Menu {
                objectName: "menuMeasure"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                accessName: "More"
                entries: [
                    { "label": "Undo", "icon": "undo" },
                    { "label": "Redo", "icon": "redo" },
                    { "label": "Settings", "icon": "settings" }
                ]
            }
        }

        Item {
            objectName: "snackHost"
            width: 480
            height: 120
            Snackbar {
                objectName: "snackMeasure"
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 24
                message: "Placed 2 of 2"
                actionText: "UNDO"
            }
        }

        MiniMonth {
            objectName: "monthMeasure"
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            year: 2026
            month: 11
            today: 5
            accessName: "November 2026"
        }
    }
}
