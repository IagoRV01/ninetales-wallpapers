import QtQuick 2.12

LoginView {
    id: root
    width: 1920
    height: 1080
    users: userModel
    sessions: sessionModel
    initialUser: userModel.lastIndex
    initialSession: sessionModel.lastIndex
    backend: sddm
    background: config.stringValue("Background")
    animation: config.stringValue("Animation")
    animationKind: config.stringValue("AnimationKind")
    customAvatar: config.stringValue("Avatar")
    customUser: config.stringValue("CustomUser")
    displayName: config.stringValue("DisplayName")
}
