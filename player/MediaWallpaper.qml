import QtQuick
import QtMultimedia

Item {
    id: root
    required property string mediaUri
    required property string kind
    property bool muted: true
    property string scaling: "fill"
    property bool announced: false
    signal ready()
    signal failed(string message)

    function announce(): void {
        if (!announced) {
            announced = true;
            ready();
        }
    }

    VideoOutput {
        id: video
        anchors.fill: parent
        visible: root.kind === "video"
        fillMode: root.scaling === "fit" ? VideoOutput.PreserveAspectFit : root.scaling === "stretch" ? VideoOutput.Stretch : VideoOutput.PreserveAspectCrop
    }

    MediaPlayer {
        id: player
        source: root.kind === "video" ? root.mediaUri : ""
        autoPlay: true
        loops: MediaPlayer.Infinite
        videoOutput: video
        audioOutput: root.muted ? null : audioLoader.item
        onErrorOccurred: (error, errorString) => root.failed(errorString)
    }

    Loader {
        id: audioLoader
        active: !root.muted
        sourceComponent: Component { AudioOutput {} }
    }

    Connections {
        target: video.videoSink
        function onVideoFrameChanged(): void { root.announce(); }
    }

    Image {
        anchors.fill: parent
        source: root.kind === "image" ? root.mediaUri : ""
        visible: root.kind === "image"
        asynchronous: true
        fillMode: root.scaling === "fit" ? Image.PreserveAspectFit : root.scaling === "stretch" ? Image.Stretch : Image.PreserveAspectCrop
        onStatusChanged: {
            if (status === Image.Ready) root.announce();
            else if (status === Image.Error) root.failed("No se pudo abrir la imagen.");
        }
    }

    AnimatedImage {
        anchors.fill: parent
        source: root.kind === "gif" ? root.mediaUri : ""
        visible: root.kind === "gif"
        asynchronous: true
        playing: true
        fillMode: root.scaling === "fit" ? Image.PreserveAspectFit : root.scaling === "stretch" ? Image.Stretch : Image.PreserveAspectCrop
        onStatusChanged: {
            if (status === Image.Ready) root.announce();
            else if (status === Image.Error) root.failed("No se pudo abrir el GIF.");
        }
    }
}
