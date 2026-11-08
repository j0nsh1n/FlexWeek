import QtQuick
import QtQuick.Layouts
import components 1.0

// Sign in, Create your account, and Reset your password: one card, three modes, the words of the
// Widgets page. Every action goes to the account bridge, which calls NativeSession.
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

    M3Palette { id: palette; theme: root.theme }

    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, card.implicitHeight + 48)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Rectangle {
            id: card
            objectName: "authSurface"
            width: root.phone ? parent.width - 32 : 420
            x: (scroller.width - width) / 2
            y: Math.max(24, (scroller.height - implicitHeight) / 2)
            implicitHeight: column.implicitHeight + 64
            height: implicitHeight
            radius: 8
            color: palette.surfaceContainerLow
            border.width: root.highContrast ? 1.5 : 0
            border.color: palette.outline

            ColumnLayout {
                id: column
                x: 32
                y: 32
                width: parent.width - 64
                spacing: 16

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    M3Icon {
                        name: "school"
                        width: 28
                        height: 28
                        color: palette.primary
                    }
                    Text {
                        objectName: "authBrand"
                        text: "FlexWeek"
                        color: palette.primary
                        font.family: M3Font.family
                        font.pixelSize: M3Font.px(22)
                        font.weight: 600
                    }
                }

                Text {
                    objectName: "authHeading"
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: bridge ? bridge.heading : ""
                    wrapMode: Text.WordWrap
                    color: palette.inkSurface
                    font.family: M3Font.family
                    font.pixelSize: M3Font.px(24)
                    font.weight: 400
                    Accessible.role: Accessible.Heading
                    Accessible.name: text
                }
                Text {
                    objectName: "authNote"
                    Layout.fillWidth: true
                    visible: text !== ""
                    horizontalAlignment: Text.AlignHCenter
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
                    label: "Username"
                    text: bridge ? bridge.username : ""
                    hint: bridge ? bridge.usernameHint : ""
                    problem: bridge ? bridge.usernameProblem : ""
                    focus: true
                    KeyNavigation.tab: root.reset ? recoveryCode.field : password.field
                    onEdited: (value) => bridge.setUsername(value)
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
                    label: "Password"
                    secret: true
                    text: bridge ? bridge.password : ""
                    hint: bridge ? bridge.passwordHint : ""
                    problem: bridge ? bridge.passwordProblem : ""
                    onEdited: (value) => bridge.setPassword(value)
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
                    label: "Recovery code"
                    text: bridge ? bridge.recoveryCode : ""
                    problem: bridge ? bridge.recoveryProblem : ""
                    KeyNavigation.tab: recoverPassword.field
                    onEdited: (value) => bridge.setRecoveryCode(value)
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
                    label: "New password"
                    secret: true
                    text: bridge ? bridge.newPassword : ""
                    problem: bridge ? bridge.newPasswordProblem : ""
                    onEdited: (value) => bridge.setNewPassword(value)
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
