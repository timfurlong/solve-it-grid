import Foundation
import ServiceManagement

enum LoginItem {
    private static let registeredKey = "loginItemRegistered"

    /// Registers the app to open at login, once. Skipped when not running from an .app bundle
    /// (e.g. `swift run`), since only the installed app should launch at login.
    static func registerIfNeeded(defaults: UserDefaults = .standard) {
        guard Bundle.main.bundleURL.pathExtension == "app" else { return }
        guard !defaults.bool(forKey: registeredKey) else { return }
        do {
            try SMAppService.mainApp.register()
            defaults.set(true, forKey: registeredKey)
        } catch {
            NSLog("%@", "Solve It Grid could not register as a login item: \(error)")
        }
        NSLog("%@", "Solve It Grid login item status: \(SMAppService.mainApp.status.rawValue)")
    }
}
