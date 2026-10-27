import QtQuick 2.12
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.4

Button {
    id: button
    style: ButtonStyle {
        padding { left: 14; right: 14; top: 12; bottom: 12 }
        label: Text {
            text: button.text
            color: "#f5edff"
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            implicitHeight: 40
            radius: 12
            color: button.pressed ? "#dd4b3a65" : button.hovered ? "#dd3c3053" : "#bb28223a"
            border.color: button.activeFocus ? "#dcc3fa" : "#607b6a94"
        }
    }
}
