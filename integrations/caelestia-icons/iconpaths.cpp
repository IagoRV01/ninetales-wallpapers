#include <QDir>
#include <QIcon>
#include <QQmlEngine>
#include <QQmlExtensionPlugin>
#include <QStandardPaths>
#include <QtQml/qqml.h>

// Loaded only by the Caelestia QML engine. No LD_PRELOAD or child environment changes.
class MintIconPathsPlugin final : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override { qmlRegisterModule(uri, 1, 0); }
    void initializeEngine(QQmlEngine *, const char *) override {
        QStringList paths{QDir::homePath() + "/.icons"};
        for (const auto &root : QStandardPaths::standardLocations(QStandardPaths::GenericDataLocation))
            paths.append(root + "/icons");
        paths.append({"/usr/local/share/icons", "/usr/share/icons"});
        paths.append(QIcon::themeSearchPaths());
        paths.removeDuplicates();
        QIcon::setThemeSearchPaths(paths);
        auto fallback = QIcon::fallbackSearchPaths();
        fallback.append("/usr/share/pixmaps");
        fallback.removeDuplicates();
        QIcon::setFallbackSearchPaths(fallback);
        QIcon::setFallbackThemeName(QDir("/usr/share/icons/Papirus").exists() ? "Papirus" : "hicolor");
        if (QIcon::themeName().isEmpty())
            QIcon::setThemeName("Mint-Y-Purple");
    }
};
#include "iconpaths.moc"
