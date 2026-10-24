import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    property var options: ({})
    property var streams: JSON.parse(Quickshell.env("NW_STREAMS") || "{}")

    FileView {
        path: Quickshell.env("NW_CONFIG")
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try { root.options = JSON.parse(text()); }
            catch (error) { console.error("NW_ERROR:Configuración no válida: " + error); }
        }
    }

    Variants {
        model: root.options.selection ? Quickshell.screens.filter(s => root.options.output === "*" || root.options.output === s.name) : []

        PanelWindow {
            id: win
            required property var modelData
            screen: modelData
            color: "black"
            WlrLayershell.namespace: "ninetales-wallpaper"
            WlrLayershell.layer: WlrLayer.Background
            WlrLayershell.exclusionMode: ExclusionMode.Ignore
            anchors { top: true; bottom: true; left: true; right: true }
            mask: Region {}

            MediaWallpaper {
                anchors.fill: parent
                mediaUri: root.streams[win.modelData.name] ?? root.options.selection?.media_uri ?? ""
                kind: root.streams[win.modelData.name] ? "video" : (root.options.selection?.kind ?? "")
                muted: root.streams[win.modelData.name] ? true : (root.options.muted ?? true)
                scaling: root.options.scaling ?? "fill"
                onReady: console.log("NW_READY:" + win.modelData.name)
                onFailed: message => console.error("NW_ERROR:" + message)
            }
        }
    }
}
