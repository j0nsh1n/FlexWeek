import QtQuick
import QtQuick.Layouts
import components 1.0

// Sign in, Create your account, and Reset your password: Option B split layout on desktop
// (animated multi-scene QML welcome panel on the left, clean form on the right), collapsing
// to a single centered card on narrow/phone widths.
FocusScope {
    id: root
    objectName: "authCard"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    readonly property string mode: bridge ? bridge.phase : "sign-in"
    readonly property bool signIn: mode === "sign-in"
    readonly property bool create: mode === "create"
    readonly property bool reset: mode === "reset"
    readonly property bool splitLayout: !phone && width >= 820
    property bool formInteracted: false

    onModeChanged: formInteracted = false

    M3Palette { id: palette; theme: root.theme }

    SignInShowcase {
        id: showcase
        visible: root.splitLayout
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: root.splitLayout ? Math.round(root.width * 0.52) : 0
        theme: root.theme
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        paused: password.activeFocus
            || recoveryCode.activeFocus
            || recoverPassword.activeFocus
            || keep.activeFocus
            || (username.activeFocus && (root.formInteracted || username.text !== ""))
    }

    Rectangle {
        visible: root.splitLayout
        anchors.left: showcase.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: palette.cardSurface
    }

    Flickable {
        id: scroller
        anchors.left: root.splitLayout ? showcase.right : parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        contentWidth: width
        contentHeight: Math.max(height, card.implicitHeight + 48)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Rectangle {
            id: card
            objectName: "authSurface"
            width: root.splitLayout
                ? Math.min(400, Math.max(300, scroller.width - 48))
                : (root.phone ? scroller.width - 32 : 420)
            x: (scroller.width - width) / 2
            y: Math.max(24, (scroller.height - implicitHeight) / 2)
            implicitHeight: column.implicitHeight + (root.splitLayout ? 32 : 64)
            height: implicitHeight
            radius: root.splitLayout ? 0 : palette.cornerFor(24)
            color: palette.cardSurface
            border.width: root.splitLayout ? 0 : (root.highContrast ? 1.5 : 1)
            border.color: root.highContrast ? palette.outline : palette.outlineVariant

            ColumnLayout {
                id: column
                x: root.splitLayout ? 8 : 32
                y: root.splitLayout ? 16 : 32
                width: parent.width - (root.splitLayout ? 16 : 64)
                spacing: 16

                RowLayout {
                    visible: !root.splitLayout
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    M3Icon {
                        name: "school"
                        width: 28
                        height: 28
                        color: palette.primary
                    }
                    Text {
                        objectName: !root.splitLayout ? "authBrand" : ""
                        text: "FlexWeek"
                        color: palette.primary
                        font.family: M3Font.heading
                        font.pixelSize: M3Font.px(22)
                        font.weight: 600
                    }
                }

                Text {
                    objectName: "authHeading"
                    Layout.fillWidth: true
                    horizontalAlignment: root.splitLayout ? Text.AlignLeft : Text.AlignHCenter
                    text: bridge ? bridge.heading : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkSurface
                    font.family: M3Font.heading
                    font.pixelSize: M3Font.px(26)
                    font.weight: 600
                    Accessible.role: Accessible.Heading
                    Accessible.name: text
                }
                Text {
                    objectName: "authNote"
                    Layout.fillWidth: true
                    visible: text !== ""
                    horizontalAlignment: root.splitLayout ? Text.AlignLeft : Text.AlignHCenter
                    text: bridge ? bridge.note : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                }

                AccountField {
                    id: username
                    objectName: "username"
                    Layout.fillWidth: true
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    ground: palette.cardSurface
                    label: "Username"
                    text: bridge ? bridge.username : ""
                    hint: bridge ? bridge.usernameHint : ""
                    problem: bridge ? bridge.usernameProblem : ""
                    focus: true
                    KeyNavigation.tab: root.reset ? recoveryCode.field : password.field
                    onEdited: (value) => { root.formInteracted = true; bridge.setUsername(value) }
                    onSubmitted: bridge.submit()
                }
                AccountField {
                    id: password
                    objectName: "password"
                    Layout.fillWidth: true
                    visible: !root.reset
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    ground: palette.cardSurface
                    label: "Password"
                    secret: true
                    text: bridge ? bridge.password : ""
                    hint: bridge ? bridge.passwordHint : ""
                    problem: bridge ? bridge.passwordProblem : ""
                    onEdited: (value) => { root.formInteracted = true; bridge.setPassword(value) }
                    onSubmitted: bridge.submit()
                }

                // Why the wrong-password line does not say which of the two was wrong.
                Button {
                    objectName: "authWhy"
                    visible: bridge && bridge.whyVisible && !root.reset
                    Layout.alignment: Qt.AlignLeft
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "text"
                    text: bridge ? bridge.whyLink : ""
                    onClicked: bridge.explainWhy()
                }

                AccountField {
                    id: recoveryCode
                    objectName: "recoveryCode"
                    Layout.fillWidth: true
                    visible: root.reset
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    ground: palette.cardSurface
                    label: "Recovery code"
                    text: bridge ? bridge.recoveryCode : ""
                    problem: bridge ? bridge.recoveryProblem : ""
                    KeyNavigation.tab: recoverPassword.field
                    onEdited: (value) => { root.formInteracted = true; bridge.setRecoveryCode(value) }
                    onSubmitted: bridge.submit()
                }
                AccountField {
                    id: recoverPassword
                    objectName: "recoverPassword"
                    Layout.fillWidth: true
                    visible: root.reset
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    ground: palette.cardSurface
                    label: "New password"
                    secret: true
                    text: bridge ? bridge.newPassword : ""
                    problem: bridge ? bridge.newPasswordProblem : ""
                    onEdited: (value) => { root.formInteracted = true; bridge.setNewPassword(value) }
                    onSubmitted: bridge.submit()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Switch {
                        id: keep
                        objectName: "keepSignedIn"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        checked: bridge ? bridge.keepSignedIn : true
                        accessName: "Keep me signed in on this computer"
                        onToggled: (on) => bridge.setKeepSignedIn(on)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Keep me signed in on this computer"
                        wrapMode: Text.WordWrap
                        color: palette.inkSurface
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(14)
                        font.weight: 500
                        MouseArea {
                            anchors.fill: parent
                            onClicked: bridge.setKeepSignedIn(!keep.checked)
                        }
                    }
                }

                Text {
                    objectName: "authStatus"
                    Layout.fillWidth: true
                    visible: text !== ""
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.statusLine : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkMuted
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(14)
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }

                Button {
                    objectName: root.signIn ? "signIn" : (root.create ? "createAccount" : "recoverAccount")
                    Layout.fillWidth: true
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "filled"
                    text: root.signIn ? "Sign in" : (root.create ? "Create account" : "Reset password")
                    enabled: !(bridge && bridge.busy)
                    onClicked: bridge.submit()
                }
                Button {
                    objectName: "forgotPassword"
                    visible: root.signIn
                    Layout.alignment: Qt.AlignHCenter
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "text"
                    text: "Forgot password"
                    onClicked: bridge.showReset()
                }
                Button {
                    objectName: "authSwitch"
                    Layout.alignment: Qt.AlignHCenter
                    theme: root.theme
                    density: root.density
                    reduceMotion: root.reduceMotion
                    highContrast: root.highContrast
                    kind: "text"
                    text: root.signIn ? "New here? Create an account"
                        : (root.create ? "Already have an account? Sign in" : "Back to sign in")
                    onClicked: root.signIn ? bridge.showCreate() : bridge.showSignIn()
                }
            }
        }
    }

    Connections {
        target: root.bridge
        function onChanged() { why.open = root.bridge.whyOpen }
    }
    Dialog {
        id: why
        objectName: "authWhyDialog"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        title: bridge ? bridge.whyTitle : ""
        body: bridge ? bridge.whyBody : ""
        confirmText: "Got it"
        dismissText: "Close"
        onConfirmed: bridge.dismissWhy()
        onDismissed: bridge.dismissWhy()
    }
}
