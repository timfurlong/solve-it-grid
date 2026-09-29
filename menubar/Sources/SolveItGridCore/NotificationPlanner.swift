import Foundation

/// What the planner remembers between polls. Persisted by the app.
public struct NotificationMemory: Codable, Equatable, Sendable {
    public var initialized: Bool
    public var checkinNotifiedDay: String?
    public var snoozedUntil: Date?
    public var seenChipIDs: Set<Int>
    public var errorSince: Date?
    public var lastErrorNotifiedAt: Date?

    public init(initialized: Bool = false, checkinNotifiedDay: String? = nil, snoozedUntil: Date? = nil,
                seenChipIDs: Set<Int> = [], errorSince: Date? = nil, lastErrorNotifiedAt: Date? = nil) {
        self.initialized = initialized
        self.checkinNotifiedDay = checkinNotifiedDay
        self.snoozedUntil = snoozedUntil
        self.seenChipIDs = seenChipIDs
        self.errorSince = errorSince
        self.lastErrorNotifiedAt = lastErrorNotifiedAt
    }
}

public enum PlannedNotification: Equatable, Sendable {
    case checkin(stepsLeft: Int)
    case chip(id: Int, body: String)
    case error(ErrorReport)
}

extension PlannedNotification {
    /// Stable per kind, so a newer notification replaces an older one instead of stacking.
    public var identifier: String {
        switch self {
        case .checkin: return "checkin"
        case let .chip(id, _): return "chip-\(id)"
        case .error: return "error"
        }
    }
}

/// Identifiers of notifications that still apply. Anything else already delivered is stale
/// (check-in done, chip moved, error cleared) and should be withdrawn.
public func activeNotificationIDs(status: Status?, failure: CLIFailure?) -> Set<String> {
    var ids = Set<String>()
    if failure == nil, status?.checkin.due == true {
        ids.insert("checkin")
    }
    for chip in status?.chips.pending ?? [] {
        ids.insert("chip-\(chip.id)")
    }
    if errorReport(failure: failure, status: status) != nil {
        ids.insert("error")
    }
    return ids
}

public let snoozeInterval: TimeInterval = 60 * 60
public let errorRepeatInterval: TimeInterval = 2 * 60 * 60

public func snoozed(_ memory: NotificationMemory, now: Date) -> NotificationMemory {
    var m = memory
    m.snoozedUntil = now.addingTimeInterval(snoozeInterval)
    return m
}

private func dayKey(_ date: Date, _ calendar: Calendar) -> String {
    let c = calendar.dateComponents([.year, .month, .day], from: date)
    return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
}

/// Decides which notifications to post on this poll. Each kind posts at most once per call,
/// so waking after a long sleep never produces a burst.
public func planNotifications(now: Date, calendar: Calendar, status: Status?, failure: CLIFailure?,
                              memory: NotificationMemory) -> (notifications: [PlannedNotification],
                                                              memory: NotificationMemory) {
    var m = memory
    var out: [PlannedNotification] = []

    if !m.initialized {
        m.seenChipIDs.formUnion(status?.chips.pending.map(\.id) ?? [])
        m.initialized = true
    }

    if failure == nil, let status, status.checkin.due {
        let today = dayKey(now, calendar)
        let shouldPost: Bool
        if let until = m.snoozedUntil {
            shouldPost = now >= until
        } else {
            shouldPost = m.checkinNotifiedDay != today
        }
        if shouldPost {
            out.append(.checkin(stepsLeft: status.checkin.steps.filter { !$0.done }.count))
            m.checkinNotifiedDay = today
            m.snoozedUntil = nil
        }
    }

    if let status {
        let labels = Dictionary(status.units.map { ($0.id, $0.label) }, uniquingKeysWith: { first, _ in first })
        for chip in status.chips.pending where !m.seenChipIDs.contains(chip.id) {
            let label = labels[chip.unit] ?? chip.unit
            out.append(.chip(id: chip.id, body: "\(label) done. Move a \(chip.color.rawValue) chip."))
            m.seenChipIDs.insert(chip.id)
        }
    }

    if let report = errorReport(failure: failure, status: status) {
        if m.errorSince == nil {
            m.errorSince = now
            m.lastErrorNotifiedAt = now
            out.append(.error(report))
        } else if let last = m.lastErrorNotifiedAt, now.timeIntervalSince(last) >= errorRepeatInterval {
            m.lastErrorNotifiedAt = now
            out.append(.error(report))
        }
    } else {
        m.errorSince = nil
        m.lastErrorNotifiedAt = nil
    }

    return (out, m)
}
