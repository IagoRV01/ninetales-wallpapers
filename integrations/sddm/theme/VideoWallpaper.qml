import QtQuick 2.12
import QtMultimedia 5.12

Video {
    property url media
    source: media
    autoPlay: true
    loops: MediaPlayer.Infinite
    muted: true
    volume: 0
    fillMode: VideoOutput.PreserveAspectCrop
}
