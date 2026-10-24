#include <QGuiApplication>
#include <QIcon>
#include <QPixmap>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QDebug>
#include <QImage>
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QIcon::setThemeName("Mint-Y-Purple");
    // Reproduce the private Qt installation's incomplete initial search path.
    QIcon::setThemeSearchPaths({":/icons"});
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QQmlComponent component(&engine);
    component.setData("import QtQml\nimport CaelestiaMint.Icons 1.0\nQtObject {}", QUrl());
    auto object = component.create();
    if (!object) { qWarning() << component.errors(); return 1; }
    int failed = 0;
    for (const auto &name : {"steam", "system-file-manager", "btop", "preferences-desktop-keyboard-shortcuts",
                              "cs-workspaces", "firefox", "claude-desktop", "image-missing"}) {
        const auto icon = QIcon::fromTheme(name);
        const bool ok = !icon.isNull() && !icon.pixmap(48,48).isNull();
        qInfo() << name << (ok ? "OK" : "FAILED");
        failed += !ok;
    }
    delete object;
    return failed ? 1 : 0;
}
