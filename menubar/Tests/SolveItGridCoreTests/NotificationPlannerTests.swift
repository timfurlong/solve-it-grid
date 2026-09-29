import Foundation
import Testing
@testable import SolveItGridCore

private var utc: Calendar {
    var c = Calendar(identifier: .gregorian)
    c.timeZone = TimeZone(identifier: "UTC")!
    return c
}

private func at(_ time: String, day: Int = 1) -> Date {
    let parts = time.split(separator: ":").map { Int($0)! }
    return utc.date(from: DateComponents(year: 2026, month: 10, day: day, hour: parts[0], minute: parts[1]))!
}

private func thursday() throws -> Status { try Status.decode(fixture("status-thursday")) }

private func plan(_ now: Date, _ status: Status?, _ memory: NotificationMemory,
                  failure: CLIFailure? = nil) -> ([PlannedNotification], NotificationMemory) {
    let r = planNotifications(now: now, calendar: utc, status: status, failure: failure, memory: memory)
    return (r.notifications, r.memory)
}

@Test func checkinPostsOnceWhenDue() throws {
    let s = try thursday()
    let (first, memory) = plan(at("09:01"), s, NotificationMemory())
    #expect(first == [.checkin(stepsLeft: 4)])
    let (second, _) = plan(at("09:02"), s, memory)
    #expect(second.isEmpty)
}

@Test func snoozeRepostsAfterAnHour() throws {
    let s = try thursday()
    var (_, memory) = plan(at("09:01"), s, NotificationMemory())
    memory = snoozed(memory, now: at("09:05"))
    #expect(plan(at("09:30"), s, memory).0.isEmpty)
    let (later, after) = plan(at("10:05"), s, memory)
    #expect(later == [.checkin(stepsLeft: 4)] && after.snoozedUntil == nil)
}

@Test func notDueNoCheckin() throws {
    var s = try thursday()
    s.checkin.due = false
    #expect(plan(at("09:01"), s, NotificationMemory()).0.isEmpty)
}

@Test func firstRunSeedsChipsWithoutNotifying() throws {
    var s = try thursday()
    s.checkin.due = false
    let (notes, memory) = plan(at("09:01"), s, NotificationMemory())
    #expect(notes.isEmpty && memory.seenChipIDs == [57] && memory.initialized)
}

@Test func newChipNotifiedOnce() throws {
    var s = try thursday()
    s.checkin.due = false
    let memory = NotificationMemory(initialized: true)
    let (notes, after) = plan(at("10:12"), s, memory)
    #expect(notes == [.chip(id: 57, body: "Home yellow done. Move a yellow chip.")])
    #expect(plan(at("10:13"), s, after).0.isEmpty)
}

@Test func errorNotifiesOnStartAndEveryTwoHours() throws {
    let failure = CLIFailure(error: .timedOut(seconds: 10), since: at("09:00"))
    let report = errorReport(failure: failure, status: nil)!
    let seeded = NotificationMemory(initialized: true, seenChipIDs: [57])
    let (start, m1) = plan(at("09:00"), nil, seeded, failure: failure)
    #expect(start == [.error(report)] && m1.errorSince == at("09:00"))
    let (hourLater, m2) = plan(at("10:00"), nil, m1, failure: failure)
    #expect(hourLater.isEmpty)
    let (twoHours, m3) = plan(at("11:00"), nil, m2, failure: failure)
    #expect(twoHours == [.error(report)])
    var fine = try thursday()
    fine.checkin.due = false
    let (cleared, m4) = plan(at("11:05"), fine, m3)
    #expect(cleared.isEmpty && m4.errorSince == nil && m4.lastErrorNotifiedAt == nil)
}

@Test func wakeAfterLongSleepPostsOneOfEach() throws {
    var s = try thursday()
    s.health = Health(ok: false, errors: [HealthError(source: "categorizer", message: "boom", since: nil)])
    let memory = NotificationMemory(initialized: true, checkinNotifiedDay: "2026-09-30", seenChipIDs: [57],
                                    errorSince: at("01:00"), lastErrorNotifiedAt: at("01:00"))
    let (notes, _) = plan(at("11:00"), s, memory)
    #expect(notes == [.checkin(stepsLeft: 4), .error(errorReport(failure: nil, status: s)!)])
}

@Test func activeNotificationIDsTrackWhatStillApplies() throws {
    let s = try thursday()
    #expect(activeNotificationIDs(status: s, failure: nil) == ["checkin", "chip-57"])
    var done = s
    done.checkin.due = false
    done.chips.pending = []
    #expect(activeNotificationIDs(status: done, failure: nil).isEmpty)
    let failure = CLIFailure(error: .timedOut(seconds: 10), since: at("09:00"))
    #expect(activeNotificationIDs(status: s, failure: failure) == ["error", "chip-57"])
}

@Test func plannedNotificationIdentifiers() {
    #expect(PlannedNotification.checkin(stepsLeft: 1).identifier == "checkin")
    #expect(PlannedNotification.chip(id: 57, body: "x").identifier == "chip-57")
}
