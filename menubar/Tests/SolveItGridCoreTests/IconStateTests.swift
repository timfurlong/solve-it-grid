import Foundation
import Testing
@testable import SolveItGridCore

private func thursday() throws -> Status { try Status.decode(fixture("status-thursday")) }
private let failure = CLIFailure(error: .timedOut(seconds: 10), since: Date(timeIntervalSince1970: 0))

@Test func errorWhenFailure() throws {
    #expect(iconState(status: try thursday(), failure: failure) == .error)
}

@Test func errorWhenHealthNotOk() throws {
    var s = try thursday()
    s.health = Health(ok: false, errors: [HealthError(source: "setup", message: "x", since: nil)])
    #expect(iconState(status: s, failure: nil) == .error)
}

@Test func segmentsFollowUnits() throws {
    guard case let .ring(segments, _) = iconState(status: try thursday(), failure: nil) else {
        Issue.record("expected ring"); return
    }
    #expect(segments == [Segment(color: .yellow, done: true), Segment(color: .yellow, done: true),
                         Segment(color: .green, done: true), Segment(color: .green, done: false)])
}

@Test func checkinDueBeatsChipWaiting() throws {
    guard case let .ring(_, center) = iconState(status: try thursday(), failure: nil) else {
        Issue.record("expected ring"); return
    }
    #expect(center == .checkinDue)
}

@Test func chipWaitingBeatsWeekHit() throws {
    var s = try thursday()
    s.checkin.due = false
    s.week.hit = true
    #expect(iconState(status: s, failure: nil) == .ring(segments: segments(s), center: .chipWaiting(.yellow)))
}

@Test func weekHitCenter() throws {
    var s = try thursday()
    s.checkin.due = false
    s.chips.pending = []
    s.week.hit = true
    #expect(iconState(status: s, failure: nil) == .ring(segments: segments(s), center: .weekHit))
}

@Test func nilStatusIsFourOpenSegments() {
    #expect(iconState(status: nil, failure: nil) == .ring(
        segments: [Segment(color: .yellow, done: false), Segment(color: .yellow, done: false),
                   Segment(color: .green, done: false), Segment(color: .green, done: false)],
        center: .none))
}

@Test func accessibilityLabels() throws {
    #expect(iconAccessibilityLabel(iconState(status: try thursday(), failure: nil))
            == "Solve It Grid: 3 of 4 done, check-in due")
    #expect(iconAccessibilityLabel(.error) == "Solve It Grid needs attention")
    #expect(iconAccessibilityLabel(iconState(status: nil, failure: nil)) == "Solve It Grid: 0 of 4 done")
}

private func segments(_ s: Status) -> [Segment] { s.units.map { Segment(color: $0.color, done: $0.done) } }
