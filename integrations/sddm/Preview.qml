import QtQuick 2.12

LoginView {
    id: view
    width: 1920
    height: 1080
    users: ListModel { id: demoUsers }
    sessions: ListModel {
        ListElement { name: "Hyprland" }
        ListElement { name: "Cinnamon" }
    }
    backend: QtObject {
        property bool canSuspend: true
        property bool canReboot: true
        property bool canPowerOff: true
        signal loginFailed()
        signal loginSucceeded()
        signal informationMessage(string message)
        function login(user, password, session) {
            if (user !== view.customUser || password !== "test-only" || session !== 1) {
                console.log("LOGIN_CHECK_FAIL: wrong login target");
                Qt.quit();
                return;
            }
            loginFailed();
        }
        function suspend() {}
        function reboot() {}
        function powerOff() {}
    }
    background: config.stringValue("Background")
    animation: config.stringValue("Animation")
    animationKind: config.stringValue("AnimationKind")
    customAvatar: config.stringValue("Avatar")
    customUser: config.stringValue("CustomUser")
    displayName: config.stringValue("DisplayName")

    function child(item, name) {
        if (item.objectName === name)
            return item;
        for (var i = 0; i < item.children.length; i++) {
            var found = child(item.children[i], name);
            if (found) return found;
        }
        return null;
    }
    Component.onCompleted: demoUsers.append({name: customUser, realName: displayName, icon: ""})
    Timer {
        interval: 1500
        running: true
        onTriggered: {
            var password = view.child(view, "password");
            var session = view.child(view, "sessionPicker");
            session.currentIndex = 1;
            password.text = "test-only";
            view.login();
            if (view.busy || password.text !== "" || view.errorMessage === "") {
                console.log("LOGIN_CHECK_FAIL: failed login must clear password and allow retry");
                Qt.quit();
                return;
            }
            view.errorMessage = "";
            view.grabToImage(function(result) {
                if (!result.saveToFile(config.stringValue("PreviewPath"))) {
                    console.log("LOGIN_CHECK_FAIL: could not save preview");
                } else {
                    console.log("LOGIN_CHECK_PASS: full theme, avatar, session selection, login failure and retry");
                }
                Qt.quit();
            });
        }
    }
}
