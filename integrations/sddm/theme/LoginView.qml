import QtQuick 2.12
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.4
import QtQuick.Layouts 1.12
import QtGraphicalEffects 1.12

Rectangle {
    id: root
    color: "#141322"
    property var users
    property var sessions
    property var backend
    property int initialUser: 0
    property int initialSession: 0
    property url background
    property url animation
    property string animationKind: "image"
    property url customAvatar
    property string customUser: ""
    property string displayName: ""
    property bool busy: false
    property string errorMessage: ""
    property date now: new Date()
    readonly property string selectedUser: userPicker.currentIndex >= 0 ? userPicker.currentText : username.text
    readonly property string selectedName: selectedUser === customUser && displayName ? displayName : (names.itemAt(userPicker.currentIndex) ? names.itemAt(userPicker.currentIndex).fullName : selectedUser)
    readonly property real uiScale: Math.min(1, width / 1100, height / 850)

    function login() {
        if (busy || !selectedUser || sessionPicker.currentIndex < 0)
            return;
        busy = true;
        errorMessage = "";
        backend.login(selectedUser, password.text, sessionPicker.currentIndex);
        password.text = "";
    }

    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }
    Connections {
        target: root.backend
        function onLoginFailed() {
            root.busy = false;
            root.errorMessage = qsTr("No se ha podido iniciar sesión. Comprueba tu contraseña.");
            password.text = "";
            password.forceActiveFocus();
        }
        function onLoginSucceeded() { password.text = ""; }
        function onInformationMessage(message) { root.errorMessage = message; }
    }

    Item {
        id: wallpaper
        anchors.fill: parent
        Image { anchors.fill: parent; source: root.background; fillMode: Image.PreserveAspectCrop; asynchronous: true }
        AnimatedImage {
            anchors.fill: parent
            visible: root.animationKind === "gif"
            source: visible ? root.animation : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
        Loader {
            anchors.fill: parent
            active: root.animationKind === "video" && root.animation.toString().length > 0
            source: active ? "VideoWallpaper.qml" : ""
            onLoaded: item.media = root.animation
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#1014192b" }
            GradientStop { position: 0.55; color: "#4015132a" }
            GradientStop { position: 1; color: "#c4141224" }
        }
    }

    Column {
        anchors.top: parent.top
        anchors.topMargin: Math.max(25, root.height * 0.045)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(root.now, "HH:mm")
            color: "#fffaff"
            font.family: "Noto Sans"
            font.pixelSize: 66 * root.uiScale
            font.weight: Font.Light
            font.letterSpacing: -2
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDate(root.now, "dddd, d MMMM")
            color: "#e8e3f5"
            font.pixelSize: 15 * root.uiScale
        }
    }

    Rectangle {
        id: card
        width: 430
        height: form.implicitHeight + 68
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 30 * root.uiScale
        scale: root.uiScale
        radius: 32
        color: "#bb242039"
        border.color: "#60f2e9ff"
        border.width: 1

        ShaderEffectSource {
            id: glassSource
            sourceItem: wallpaper
            sourceRect: Qt.rect(card.x, card.y, card.width, card.height)
            visible: false
            live: true
        }
        FastBlur {
            anchors.fill: parent
            source: glassSource
            radius: 48
            opacity: 0.35
            layer.enabled: true
            layer.effect: OpacityMask { maskSource: Rectangle { width: card.width; height: card.height; radius: card.radius } }
        }

        ColumnLayout {
            id: form
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 34
            spacing: 15

            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 108
                Layout.preferredHeight: 108
                Rectangle { anchors.fill: parent; radius: width / 2; color: "#81759d"; border.color: "#b6a7dd"; border.width: 2 }
                Text { anchors.centerIn: parent; text: root.selectedName.slice(0, 1).toUpperCase(); color: "white"; font.pixelSize: 44 }
                Image {
                    anchors.fill: parent
                    anchors.margins: 3
                    source: root.selectedUser === root.customUser ? root.customAvatar : (names.itemAt(userPicker.currentIndex) ? names.itemAt(userPicker.currentIndex).avatar : "")
                    fillMode: Image.PreserveAspectCrop
                }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.selectedName || qsTr("Bienvenido")
                color: "#fffbff"
                font.pixelSize: 26
                font.weight: Font.DemiBold
                maximumLineCount: 1
                elide: Text.ElideRight
                Layout.maximumWidth: parent.width
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Tu espacio, a un paso.")
                color: "#c6bdda"
                font.pixelSize: 13
            }
            ComboBox {
                id: userPicker
                objectName: "userPicker"
                Layout.fillWidth: true
                model: root.users
                textRole: "name"
                currentIndex: Math.max(0, root.initialUser)
                visible: count > 1
                onCurrentIndexChanged: { password.text = ""; root.errorMessage = ""; }
            }
            Repeater {
                id: names
                model: root.users
                delegate: Item {
                    visible: false
                    property string fullName: model.realName || model.name
                    property string avatar: model.icon || ""
                }
            }
            TextField {
                id: username
                Layout.fillWidth: true
                visible: userPicker.count === 0
                placeholderText: qsTr("Usuario")
                textColor: "#fffaff"
                selectByMouse: true
                onAccepted: password.forceActiveFocus()
            }
            TextField {
                id: password
                objectName: "password"
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                placeholderText: qsTr("Contraseña")
                textColor: "#fffaff"
                echoMode: TextInput.Password
                selectByMouse: true
                enabled: !root.busy
                focus: true
                font.pixelSize: 15
                style: TextFieldStyle {
                    padding { top: 14; bottom: 14; left: 18; right: 18 }
                    textColor: "#fffaff"
                    placeholderTextColor: "#c3b9d2"
                    passwordCharacter: "●"
                    background: Rectangle { radius: 15; color: "#68201b32"; border.width: 1; border.color: password.activeFocus ? "#d3baff" : "#706e5a88" }
                }
                onAccepted: root.login()
                Keys.onEscapePressed: text = ""
                Component.onCompleted: forceActiveFocus()
            }
            Text {
                Layout.fillWidth: true
                text: root.errorMessage
                visible: text.length > 0
                wrapMode: Text.WordWrap
                color: "#ffcec7"
                font.pixelSize: 12
            }
            Button {
                id: loginButton
                objectName: "loginButton"
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                enabled: !root.busy && root.selectedUser.length > 0 && sessionPicker.currentIndex >= 0
                text: root.busy ? qsTr("Entrando…") : qsTr("Iniciar sesión  →")
                style: ButtonStyle {
                    label: Text { text: loginButton.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "#23172f"; font.pixelSize: 15; font.weight: Font.DemiBold }
                    background: Rectangle { radius: 15; color: loginButton.pressed ? "#bc9ae6" : loginButton.hovered ? "#eddaff" : "#dcc3fa"; opacity: loginButton.enabled ? 1 : 0.6 }
                }
                onClicked: root.login()
            }
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Math.max(20, root.width * 0.027)
        spacing: 12
        ComboBox {
            id: sessionPicker
            objectName: "sessionPicker"
            Layout.preferredWidth: Math.min(240, root.width * 0.33)
            model: root.sessions
            textRole: "name"
            currentIndex: Math.max(0, root.initialSession)
            Accessible.name: qsTr("Sesión de escritorio")
            style: ComboBoxStyle {
                textColor: "#f5edff"
                background: Rectangle { implicitHeight: 40; radius: 12; color: "#bb28223a"; border.color: "#607b6a94" }
                label: Text { text: sessionPicker.currentText + "  ▾"; color: "#f5edff"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; leftPadding: 12 }
            }
        }
        Item { Layout.fillWidth: true }
        ActionButton { text: qsTr("Suspender"); visible: root.backend && root.backend.canSuspend; onClicked: root.backend.suspend() }
        ActionButton { text: qsTr("Reiniciar"); visible: root.backend && root.backend.canReboot; onClicked: root.backend.reboot() }
        ActionButton { text: qsTr("Apagar"); visible: root.backend && root.backend.canPowerOff; onClicked: root.backend.powerOff() }
    }
}
