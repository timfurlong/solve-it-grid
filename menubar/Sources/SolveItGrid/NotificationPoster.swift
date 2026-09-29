import Foundation
import SolveItGridCore
import UserNotifications

/// Posts the planner's notifications and routes their buttons back to the app.
@MainActor
final class NotificationPoster: NSObject, UNUserNotificationCenterDelegate {
    var onOpen: (() -> Void)?
    var onSnooze: (() -> Void)?

    private static let checkinCategory = "CHECKIN"
    private static let startAction = "START"
    private static let snoozeAction = "SNOOZE"

    /// UNUserNotificationCenter throws when the process isn't an .app bundle (e.g. `swift run`),
    /// so notifications are simply off there.
    private let inBundle = Bundle.main.bundleURL.pathExtension == "app"
    private lazy var center = UNUserNotificationCenter.current()

    func configure() {
        guard inBundle else { return }
        center.delegate = self
        let start = UNNotificationAction(identifier: Self.startAction, title: "Start check-in", options: [.foreground])
        let snooze = UNNotificationAction(identifier: Self.snoozeAction, title: "Snooze 1 hour", options: [])
        center.setNotificationCategories([
            UNNotificationCategory(identifier: Self.checkinCategory, actions: [start, snooze], intentIdentifiers: []),
        ])
    }

    func requestAuthorization() {
        guard inBundle else { return }
        center.requestAuthorization(options: [.alert, .sound]) { granted, error in
            NSLog("%@", "Solve It Grid notifications authorized: \(granted) \(error.map { "\($0)" } ?? "")")
        }
    }

    func post(_ notification: PlannedNotification) {
        guard inBundle else { return }
        let content = UNMutableNotificationContent()
        let identifier = notification.identifier
        switch notification {
        case let .checkin(stepsLeft):
            content.title = "Time for your check-in"
            content.body = Copy.stepsLeftBody(stepsLeft)
            content.categoryIdentifier = Self.checkinCategory
            // Honored only if the app holds the time-sensitive entitlement; otherwise delivered as active.
            content.interruptionLevel = .timeSensitive
        case let .chip(_, body):
            content.title = "Chip earned"
            content.body = body
        case let .error(report):
            content.title = "Solve It Grid needs attention"
            content.body = [report.detail, report.fix].compactMap { $0 }.joined(separator: "\n")
        }
        content.sound = .default
        center.add(UNNotificationRequest(identifier: identifier, content: content, trigger: nil)) { error in
            if let error { NSLog("%@", "Solve It Grid could not post \(identifier): \(error)") }
        }
    }

    /// Removes delivered notifications that no longer apply (check-in done, chip moved, error
    /// cleared), so Persistent alerts don't linger after the popover handled them.
    func withdraw(keeping active: Set<String>) {
        guard inBundle else { return }
        center.getDeliveredNotifications { delivered in
            let stale = delivered.map(\.request.identifier).filter { !active.contains($0) }
            if !stale.isEmpty {
                UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: stale)
            }
        }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            didReceive response: UNNotificationResponse,
                                            withCompletionHandler completionHandler: @escaping () -> Void) {
        let action = response.actionIdentifier
        Task { @MainActor in
            if action == Self.snoozeAction {
                self.onSnooze?()
            } else {
                self.onOpen?()  // Start check-in, or a tap on any of our notifications
            }
            completionHandler()
        }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification,
                                            withCompletionHandler completionHandler:
                                            @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
}
