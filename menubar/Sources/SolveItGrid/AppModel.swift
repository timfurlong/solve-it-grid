import Foundation
import Observation
import SolveItGridCore

/// Holds the latest status and runs every CLI call. Views and the status item observe it.
@MainActor
@Observable
final class AppModel {
    /// The last status that decoded successfully; kept on screen while an error is shown.
    private(set) var status: Status?
    /// The failure the banner, icon and notifications report. Nil while a lone timeout is held back.
    private(set) var failure: CLIFailure?
    /// Every failed poll in the current run, shown or not.
    @ObservationIgnored private var failureRun: CLIFailure?
    private(set) var memory: NotificationMemory

    @ObservationIgnored var onChange: (() -> Void)?
    @ObservationIgnored var onNotify: (([PlannedNotification]) -> Void)?
    @ObservationIgnored private let defaults: UserDefaults
    /// Called after each refresh with the notification identifiers that still apply.
    @ObservationIgnored var onSync: ((Set<String>) -> Void)?
    @ObservationIgnored private let gate = RefreshGate()

    private static let memoryKey = "notificationMemory"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.memoryKey),
           let saved = try? JSONDecoder().decode(NotificationMemory.self, from: data) {
            memory = saved
        } else {
            memory = NotificationMemory()
        }
    }

    var icon: IconState { iconState(status: status, failure: failure) }

    private var client: CLIClient { CLIClient(executable: CLIClient.defaultExecutable(defaults: defaults)) }

    /// Refreshes status; a request that arrives mid-refresh triggers one more pass rather than
    /// being dropped, so the result of an action (a chip ack, a tick) always shows.
    func refresh() async {
        await gate.run { [weak self] in await self?.fetchAndPlan() }
    }

    private func fetchAndPlan() async {
        do {
            status = try await client.status()
            failureRun = nil
        } catch let error as CLIError {
            failureRun = .next(error, after: failureRun, now: Date())
        } catch {
            failureRun = .next(.failed(exitCode: -1, stderr: String(describing: error)), after: failureRun,
                               now: Date())
        }
        failure = failureRun?.isShown == true ? failureRun : nil
        let planned = planNotifications(now: Date(), calendar: .current, status: status, failure: failure,
                                        memory: memory)
        memory = planned.memory
        saveMemory()
        onChange?()
        onSync?(activeNotificationIDs(status: failure == nil ? status : nil, failure: failure))
        if !planned.notifications.isEmpty {
            onNotify?(planned.notifications)
        }
    }

    /// Shows a given status without calling the CLI (snapshots only).
    func show(_ status: Status) {
        self.status = status
        failureRun = nil
        failure = nil
    }

    func ackAll() async {
        guard let status else { return }
        await perform { try await $0.ackChips(chipBoard(for: status).pendingIDs) }
    }

    func checkinDone() async {
        await perform { try await $0.checkinDone() }
    }

    func tick(_ step: String) async {
        await perform { try await $0.tick(step) }
    }

    func snooze() {
        memory = snoozed(memory, now: Date())
        saveMemory()
    }

    private func perform(_ action: (CLIClient) async throws -> Void) async {
        do {
            try await action(client)
        } catch {
            NSLog("%@", "Solve It Grid action failed: \(error)")
        }
        await refresh()
    }

    private func saveMemory() {
        if let data = try? JSONEncoder().encode(memory) {
            defaults.set(data, forKey: Self.memoryKey)
        }
    }
}
