import QtQuick
import components 1.0

// Left welcome panel for Sign In (Option B): cycles smoothly through five theme-drawn QML
// FlexWeek scenes with captions, indicator dots, pause on hover, and a single static scene
// when Reduce motion or Animations Off is active.
Item {
    id: root
    objectName: "signInShowcase"
    property var theme
    property bool reduceMotion: false
    property bool highContrast: false
    readonly property bool staticMode: root.reduceMotion || Motion.pace <= 0
    readonly property bool autoAdvancing: slideTimer.running
    property int slideIntervalMs: 4800
    property int currentSlide: 0

    readonly property var slides: [
        {
            title: "Your whole week, planned around school",
            caption: "Drop homework into open gaps or let FlexWeek place it before each deadline."
        },
        {
            title: "Know what comes next, right now",
            caption: "A full-height day timeline beside a live Now card and mini-month."
        },
        {
            title: "See today's progress at a glance",
            caption: "One progress ring and side-by-side Up next and Done cards keep today calm."
        },
        {
            title: "Stay with one assignment at a time",
            caption: "A distraction-free countdown timer with breaks and optional ambient audio."
        },
        {
            title: "In step with your phone, privately",
            caption: "Pair with a one-time code over an encrypted relay — your week stays yours."
        }
    ]

    onStaticModeChanged: {
        if (staticMode)
            currentSlide = 0
    }

    M3Palette { id: pal; theme: root.theme }
    readonly property var classTone: pal.classFor("class")
    readonly property var sportTone: pal.classFor("exercise")
    readonly property var hwTone: pal.classFor("assignments")
    readonly property color nowAccent: pal.tone("nowLine", pal.primary)

    // Tonal background with subtle primary wash
    Rectangle {
        anchors.fill: parent
        color: pal.panelSurface
        Rectangle {
            anchors.fill: parent
            opacity: pal.dark ? 0.16 : 0.35
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: pal.primaryContainer }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // Subtle right divider separating showcase from form panel
    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: pal.outlineVariant
    }

    HoverHandler { id: panelHover }

    Timer {
        id: slideTimer
        objectName: "signInSlideTimer"
        interval: root.slideIntervalMs
        repeat: true
        running: root.visible && !root.staticMode && !panelHover.hovered
        onTriggered: root.currentSlide = (root.currentSlide + 1) % root.slides.length
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.leftMargin: Math.max(32, parent.width * 0.08)
        anchors.rightMargin: Math.max(32, parent.width * 0.08)
        anchors.topMargin: 32
        anchors.bottomMargin: 28

        // Brand header
        Row {
            id: brandRow
            anchors.top: parent.top
            anchors.left: parent.left
            spacing: 12
            Rectangle {
                width: 40
                height: 40
                radius: pal.cornerFor(12)
                color: pal.primary
                M3Icon {
                    anchors.centerIn: parent
                    name: "school"
                    width: 22
                    height: 22
                    color: pal.inkPrimary
                }
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1
                Text {
                    objectName: root.visible ? "authBrand" : ""
                    text: "FlexWeek"
                    color: pal.inkSurface
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(20)
                    font.weight: 700
                }
                Text {
                    text: "Plan your week calmly"
                    color: pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(12)
                }
            }
        }

        // Center animated showcase stage + caption + dots
        Column {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 18

            // Elevated miniature showcase frame
            Item {
                id: stage
                width: Math.min(parent.width, 460)
                height: 276
                anchors.horizontalCenter: parent.horizontalCenter
                clip: true

                // Slide 0: Week view with auto-placed homework
                Item {
                    id: slide0
                    readonly property bool active: root.currentSlide === 0
                    anchors.fill: parent
                    opacity: active ? 1.0 : 0.0
                    y: active ? 0 : (root.staticMode ? 0 : 14)
                    scale: active ? 1.0 : (root.staticMode ? 1.0 : 0.96)
                    visible: opacity > 0.01
                    Behavior on opacity { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(320, root.reduceMotion) } }
                    Behavior on y { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }
                    Behavior on scale { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: pal.cornerFor(18)
                        color: pal.cardSurface
                        border.width: 1
                        border.color: pal.outlineVariant
                        clip: true

                        // Mini top bar
                        Item {
                            id: wTop
                            x: 16; y: 12; width: parent.width - 32; height: 28
                            Text {
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Nov 23 – 27"
                                color: pal.inkSurface
                                font.family: M3Font.heading
                                font.pixelSize: 13
                                font.weight: 600
                            }
                            Rectangle {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: planLbl.implicitWidth + 20
                                height: 24
                                radius: 12
                                color: pal.primary
                                Row {
                                    anchors.centerIn: parent
                                    spacing: 4
                                    M3Icon { name: "auto_awesome"; width: 12; height: 12; color: pal.inkPrimary; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        id: planLbl
                                        text: "Plan homework"
                                        color: pal.inkPrimary
                                        font.family: M3Font.family
                                        font.pixelSize: 10
                                        font.weight: 600
                                    }
                                }
                            }
                        }

                        // Mini 5-day columns
                        Row {
                            x: 16; y: 48; width: parent.width - 32; height: parent.height - 62
                            spacing: 6
                            Repeater {
                                model: [
                                    { d: "Mon", today: false, hw: "Math", hwY: 84, hwH: 46, sport: false },
                                    { d: "Tue", today: false, hw: "", hwY: 0, hwH: 0, sport: true },
                                    { d: "Wed", today: false, hw: "Lab", hwY: 88, hwH: 52, sport: false },
                                    { d: "Thu", today: true, hw: "Essay", hwY: 96, hwH: 54, sport: true },
                                    { d: "Fri", today: false, hw: "Quiz", hwY: 78, hwH: 42, sport: false }
                                ]
                                Item {
                                    required property var modelData
                                    width: (parent.width - 24) / 5
                                    height: parent.height

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 8
                                        color: modelData.today ? pal.secondaryContainer : pal.panelSurface
                                        opacity: modelData.today ? 0.45 : 0.5
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        y: 6
                                        text: modelData.d
                                        color: modelData.today ? pal.primary : pal.inkMuted
                                        font.family: M3Font.family
                                        font.pixelSize: 10
                                        font.weight: modelData.today ? 700 : 500
                                    }
                                    // School block
                                    Rectangle {
                                        x: 4; y: 24; width: parent.width - 8; height: 48
                                        radius: 6
                                        color: root.classTone.fill
                                        Rectangle { width: 3; height: parent.height - 8; x: 2; y: 4; radius: 1.5; color: root.classTone.bar }
                                        Text {
                                            x: 8; y: 6
                                            text: "School"
                                            color: root.classTone.ink
                                            font.family: M3Font.family
                                            font.pixelSize: 9
                                            font.weight: 600
                                        }
                                    }
                                    // Optional sport block
                                    Rectangle {
                                        visible: modelData.sport
                                        x: 4; y: 156; width: parent.width - 8; height: 34
                                        radius: 6
                                        color: root.sportTone.fill
                                        Rectangle { width: 3; height: parent.height - 8; x: 2; y: 4; radius: 1.5; color: root.sportTone.bar }
                                        Text {
                                            x: 8; y: 6
                                            text: "Soccer"
                                            color: root.sportTone.ink
                                            font.family: M3Font.family
                                            font.pixelSize: 9
                                            font.weight: 600
                                        }
                                    }
                                    // Auto-placed homework block
                                    Rectangle {
                                        visible: modelData.hw !== ""
                                        x: 4; y: modelData.hwY; width: parent.width - 8; height: modelData.hwH
                                        radius: 6
                                        color: root.hwTone.fill
                                        border.width: modelData.today ? 1 : 0
                                        border.color: root.hwTone.bar
                                        Rectangle { width: 3; height: parent.height - 8; x: 2; y: 4; radius: 1.5; color: root.hwTone.bar }
                                        Text {
                                            x: 8; y: 6
                                            text: modelData.hw
                                            color: root.hwTone.ink
                                            font.family: M3Font.family
                                            font.pixelSize: 9
                                            font.weight: 600
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Slide 1: Day timeline + right Now card + mini-month
                Item {
                    id: slide1
                    readonly property bool active: root.currentSlide === 1
                    anchors.fill: parent
                    opacity: active ? 1.0 : 0.0
                    y: active ? 0 : (root.staticMode ? 0 : 14)
                    scale: active ? 1.0 : (root.staticMode ? 1.0 : 0.96)
                    visible: opacity > 0.01
                    Behavior on opacity { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(320, root.reduceMotion) } }
                    Behavior on y { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }
                    Behavior on scale { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }

                    Row {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 10

                        // Left timeline card
                        Rectangle {
                            width: (parent.width - 10) * 0.58
                            height: parent.height
                            radius: pal.cornerFor(16)
                            color: pal.cardSurface
                            border.width: 1
                            border.color: pal.outlineVariant
                            clip: true

                            Column {
                                x: 12; y: 12; width: parent.width - 24; spacing: 8
                                Text {
                                    text: "Thursday · 1 thing left"
                                    color: pal.inkSurface
                                    font.family: M3Font.heading
                                    font.pixelSize: 11
                                    font.weight: 600
                                }
                                Rectangle {
                                    width: parent.width; height: 54; radius: 8; color: root.classTone.fill
                                    Rectangle { width: 3; height: parent.height - 8; x: 2; y: 4; radius: 1.5; color: root.classTone.bar }
                                    Text { x: 10; y: 8; text: "School · 08:00–14:30"; color: root.classTone.ink; font.family: M3Font.family; font.pixelSize: 10; font.weight: 600 }
                                }
                                // Now indicator line
                                Row {
                                    width: parent.width; spacing: 4
                                    Rectangle { width: 7; height: 7; radius: 3.5; color: root.nowAccent; anchors.verticalCenter: parent.verticalCenter }
                                    Rectangle { width: parent.width - 11; height: 2; color: root.nowAccent; anchors.verticalCenter: parent.verticalCenter }
                                }
                                Rectangle {
                                    width: parent.width; height: 64; radius: 8; color: root.hwTone.fill
                                    Rectangle { width: 3; height: parent.height - 8; x: 2; y: 4; radius: 1.5; color: root.hwTone.bar }
                                    Column {
                                        x: 10; y: 8; spacing: 2
                                        Text { text: "History essay"; color: root.hwTone.ink; font.family: M3Font.family; font.pixelSize: 11; font.weight: 600 }
                                        Text { text: "18:45–19:45 · Due tomorrow"; color: root.hwTone.ink; opacity: 0.8; font.family: M3Font.family; font.pixelSize: 9 }
                                    }
                                }
                            }
                        }

                        // Right sidebar: Now card + Mini-month
                        Column {
                            width: (parent.width - 10) * 0.42
                            height: parent.height
                            spacing: 10

                            Rectangle {
                                width: parent.width
                                height: 122
                                radius: pal.cornerFor(16)
                                color: pal.primaryContainer
                                Column {
                                    x: 12; y: 12; width: parent.width - 24; spacing: 4
                                    Text { text: "NOW"; color: pal.primary; font.family: M3Font.family; font.pixelSize: 9; font.weight: 700; font.letterSpacing: 0.8 }
                                    Text { text: "Free for 1 h 45 m"; color: pal.inkPrimaryContainer; font.family: M3Font.heading; font.pixelSize: 13; font.weight: 700; width: parent.width; elide: Text.ElideRight }
                                    Text { text: "Next: History essay"; color: pal.inkPrimaryContainer; opacity: 0.85; font.family: M3Font.family; font.pixelSize: 10; width: parent.width; elide: Text.ElideRight }
                                    Item { width: 1; height: 6 }
                                    Rectangle {
                                        width: parent.width; height: 26; radius: 13; color: pal.primary
                                        Text { anchors.centerIn: parent; text: "Start essay"; color: pal.inkPrimary; font.family: M3Font.family; font.pixelSize: 10; font.weight: 600 }
                                    }
                                }
                            }

                            Rectangle {
                                width: parent.width
                                height: parent.height - 132
                                radius: pal.cornerFor(16)
                                color: pal.cardSurface
                                border.width: 1
                                border.color: pal.outlineVariant
                                Column {
                                    x: 12; y: 10; width: parent.width - 24; spacing: 8
                                    Text { text: "November"; color: pal.inkSurface; font.family: M3Font.heading; font.pixelSize: 11; font.weight: 600 }
                                    Grid {
                                        columns: 7
                                        spacing: 4
                                        Repeater {
                                            model: 21
                                            Rectangle {
                                                required property int index
                                                width: 15; height: 15; radius: 7.5
                                                color: index === 11 ? pal.primary : "transparent"
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: String(index + 10)
                                                    color: index === 11 ? pal.inkPrimary : pal.inkMuted
                                                    font.family: M3Font.family
                                                    font.pixelSize: 8
                                                    font.weight: index === 11 ? 700 : 400
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Slide 2: My day hero banner + side-by-side Up next & Done
                Item {
                    id: slide2
                    readonly property bool active: root.currentSlide === 2
                    anchors.fill: parent
                    opacity: active ? 1.0 : 0.0
                    y: active ? 0 : (root.staticMode ? 0 : 14)
                    scale: active ? 1.0 : (root.staticMode ? 1.0 : 0.96)
                    visible: opacity > 0.01
                    Behavior on opacity { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(320, root.reduceMotion) } }
                    Behavior on y { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }
                    Behavior on scale { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }

                    Column {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 10

                        // Unified hero banner
                        Rectangle {
                            width: parent.width
                            height: 108
                            radius: pal.cornerFor(18)
                            color: pal.primaryContainer
                            Row {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 14
                                Rectangle {
                                    width: 78; height: 78; radius: 39
                                    color: pal.cardSurface
                                    anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 64; height: 64; radius: 32
                                        color: "transparent"
                                        border.width: 5
                                        border.color: pal.primary
                                    }
                                    Column {
                                        anchors.centerIn: parent
                                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "1"; color: pal.inkSurface; font.family: M3Font.heading; font.pixelSize: 20; font.weight: 700 }
                                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "left"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 9 }
                                    }
                                }
                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - 92
                                    spacing: 3
                                    Text { text: "NOW"; color: pal.primary; font.family: M3Font.family; font.pixelSize: 9; font.weight: 700; font.letterSpacing: 0.8 }
                                    Text { text: "Free for 1 h 45 min"; color: pal.inkPrimaryContainer; font.family: M3Font.heading; font.pixelSize: 16; font.weight: 700 }
                                    Text { text: "Next: History essay at 18:45"; color: pal.inkPrimaryContainer; opacity: 0.85; font.family: M3Font.family; font.pixelSize: 11 }
                                }
                            }
                        }

                        // Side-by-side Up next and Done cards
                        Row {
                            width: parent.width
                            height: parent.height - 118
                            spacing: 10
                            Rectangle {
                                width: (parent.width - 10) / 2
                                height: parent.height
                                radius: pal.cornerFor(14)
                                color: pal.cardSurface
                                border.width: 1
                                border.color: pal.outlineVariant
                                Column {
                                    x: 12; y: 12; width: parent.width - 24; spacing: 8
                                    Text { text: "Up next · 1"; color: pal.inkSurface; font.family: M3Font.heading; font.pixelSize: 11; font.weight: 600 }
                                    Rectangle {
                                        width: parent.width; height: 48; radius: 8; color: root.hwTone.fill
                                        Column {
                                            x: 10; y: 8; spacing: 2
                                            Text { text: "History essay"; color: root.hwTone.ink; font.family: M3Font.family; font.pixelSize: 11; font.weight: 600 }
                                            Text { text: "18:45–19:45"; color: root.hwTone.ink; opacity: 0.8; font.family: M3Font.family; font.pixelSize: 9 }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: (parent.width - 10) / 2
                                height: parent.height
                                radius: pal.cornerFor(14)
                                color: pal.cardSurface
                                border.width: 1
                                border.color: pal.outlineVariant
                                Column {
                                    x: 12; y: 12; width: parent.width - 24; spacing: 8
                                    Row {
                                        spacing: 6
                                        Text { text: "Done"; color: pal.inkSurface; font.family: M3Font.heading; font.pixelSize: 11; font.weight: 600; anchors.verticalCenter: parent.verticalCenter }
                                        Rectangle {
                                            width: 20; height: 16; radius: 8; color: pal.statusDoneTint
                                            Text { anchors.centerIn: parent; text: "2"; color: pal.statusDone; font.family: M3Font.family; font.pixelSize: 9; font.weight: 700 }
                                        }
                                    }
                                    Rectangle {
                                        width: parent.width; height: 34; radius: 8; color: pal.panelSurface
                                        Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "School · 08:00–14:30"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 10 }
                                    }
                                    Rectangle {
                                        width: parent.width; height: 34; radius: 8; color: pal.panelSurface
                                        Text { x: 10; anchors.verticalCenter: parent.verticalCenter; text: "Soccer · 15:00–16:30"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 10 }
                                    }
                                }
                            }
                        }
                    }
                }

                // Slide 3: Focus timer countdown
                Item {
                    id: slide3
                    readonly property bool active: root.currentSlide === 3
                    anchors.fill: parent
                    opacity: active ? 1.0 : 0.0
                    y: active ? 0 : (root.staticMode ? 0 : 14)
                    scale: active ? 1.0 : (root.staticMode ? 1.0 : 0.96)
                    visible: opacity > 0.01
                    Behavior on opacity { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(320, root.reduceMotion) } }
                    Behavior on y { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }
                    Behavior on scale { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: pal.cornerFor(18)
                        color: pal.cardSurface
                        border.width: 1
                        border.color: pal.outlineVariant

                        Column {
                            anchors.centerIn: parent
                            spacing: 12
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 132; height: 132; radius: 66
                                color: pal.panelSurface
                                border.width: 7
                                border.color: pal.primary
                                Column {
                                    anchors.centerIn: parent
                                    spacing: 2
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "24:18"
                                        color: pal.inkSurface
                                        font.family: "JetBrains Mono, monospace"
                                        font.pixelSize: 26
                                        font.weight: 700
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "Focus · 1 of 4"
                                        color: pal.primary
                                        font.family: M3Font.family
                                        font.pixelSize: 10
                                        font.weight: 600
                                    }
                                }
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "History essay"
                                color: pal.inkSurface
                                font.family: M3Font.heading
                                font.pixelSize: 16
                                font.weight: 600
                            }
                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 8
                                Rectangle {
                                    width: 84; height: 30; radius: 15; color: pal.primary
                                    Text { anchors.centerIn: parent; text: "Pause"; color: pal.inkPrimary; font.family: M3Font.family; font.pixelSize: 11; font.weight: 600 }
                                }
                                Rectangle {
                                    width: 108; height: 30; radius: 15; color: pal.secondaryContainer
                                    Text { anchors.centerIn: parent; text: "Mark finished"; color: pal.inkSecondaryContainer; font.family: M3Font.family; font.pixelSize: 11; font.weight: 600 }
                                }
                            }
                        }
                    }
                }

                // Slide 4: Phone & sync
                Item {
                    id: slide4
                    readonly property bool active: root.currentSlide === 4
                    anchors.fill: parent
                    opacity: active ? 1.0 : 0.0
                    y: active ? 0 : (root.staticMode ? 0 : 14)
                    scale: active ? 1.0 : (root.staticMode ? 1.0 : 0.96)
                    visible: opacity > 0.01
                    Behavior on opacity { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(320, root.reduceMotion) } }
                    Behavior on y { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }
                    Behavior on scale { enabled: !root.staticMode; NumberAnimation { duration: Motion.travel(360, root.reduceMotion); easing.type: Easing.OutCubic } }

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: pal.cornerFor(18)
                        color: pal.cardSurface
                        border.width: 1
                        border.color: pal.outlineVariant

                        Column {
                            anchors.centerIn: parent
                            spacing: 18
                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 18
                                Column {
                                    spacing: 6
                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: 60; height: 60; radius: pal.cornerFor(16)
                                        color: pal.primaryContainer
                                        M3Icon { anchors.centerIn: parent; name: "computer"; width: 28; height: 28; color: pal.primary }
                                    }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Desktop"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 11; font.weight: 500 }
                                }
                                Row {
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 6
                                    Rectangle { width: 24; height: 2; color: pal.primary; opacity: 0.4; anchors.verticalCenter: parent.verticalCenter }
                                    Rectangle {
                                        width: 34; height: 34; radius: 17; color: pal.primary
                                        M3Icon { anchors.centerIn: parent; name: "sync"; width: 18; height: 18; color: pal.inkPrimary }
                                    }
                                    Rectangle { width: 24; height: 2; color: pal.primary; opacity: 0.4; anchors.verticalCenter: parent.verticalCenter }
                                }
                                Column {
                                    spacing: 6
                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: 60; height: 60; radius: pal.cornerFor(16)
                                        color: pal.primaryContainer
                                        M3Icon { anchors.centerIn: parent; name: "smartphone"; width: 28; height: 28; color: pal.primary }
                                    }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Phone"; color: pal.inkMuted; font.family: M3Font.family; font.pixelSize: 11; font.weight: 500 }
                                }
                            }
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: syncedRow.implicitWidth + 24
                                height: 30
                                radius: 15
                                color: pal.statusDoneTint
                                Row {
                                    id: syncedRow
                                    anchors.centerIn: parent
                                    spacing: 6
                                    M3Icon { name: "check"; width: 14; height: 14; color: pal.statusDone; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Synced · Encrypted end-to-end"; color: pal.statusDone; font.family: M3Font.family; font.pixelSize: 11; font.weight: 600 }
                                }
                            }
                        }
                    }
                }
            }

            // Slide caption
            Column {
                width: Math.min(parent.width, 440)
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6

                Text {
                    objectName: "signInSlideTitle"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.slides[root.currentSlide].title
                    color: pal.inkSurface
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(20)
                    font.weight: 600
                }
                Text {
                    objectName: "signInSlideSubtitle"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.slides[root.currentSlide].caption
                    color: pal.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                }
            }

            // Subtle indicator dots (hidden under Reduce motion / Animations Off)
            Row {
                objectName: "signInSlideDots"
                visible: !root.staticMode
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 8
                Repeater {
                    model: root.slides.length
                    Rectangle {
                        required property int index
                        objectName: "signInDot" + index
                        readonly property bool active: root.currentSlide === index
                        width: active ? 24 : 8
                        height: 8
                        radius: 4
                        color: active ? pal.primary : pal.outlineVariant
                        Behavior on width { enabled: !root.staticMode; NumberAnimation { duration: Motion.fade(220, root.reduceMotion) } }
                        TapHandler {
                            onTapped: {
                                root.currentSlide = index
                                // Do not restart while hovered or paused; the running binding resumes when the pointer leaves.
                                if (slideTimer.running)
                                    slideTimer.restart()
                            }
                        }
                    }
                }
            }
        }

        // Bottom local-first trust line
        Row {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            M3Icon {
                name: "verified_user"
                width: 16
                height: 16
                anchors.verticalCenter: parent.verticalCenter
                color: pal.inkMuted
            }
            Text {
                text: "Your week is saved on this computer, under your account."
                color: pal.inkMuted
                font.family: M3Font.family
                font.pixelSize: M3Font.px(12)
            }
        }
    }
}
