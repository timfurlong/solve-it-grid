import Foundation
import Testing
@testable import SolveItGridCore

@Test func decodesThursdayFixture() throws {
    let s = try Status.decode(fixture("status-thursday"))
    #expect(s.units.map(\.id) == ["yellow-work", "yellow-home", "green-1", "green-2"])
    #expect(s.chips.pending.first?.weekStart == "2026-09-28")
    #expect(s.redDone == 3 && s.streak == Streak(current: 3, best: 5))
    #expect(s.checkin.steps.filter(\.manual).map(\.id) == ["today-reviewed", "colors-reviewed"])
    #expect(s.lastWeek == LastWeek(start: "2026-09-21", hit: true))
    #expect(s.history.map(\.unitsDone) == [4, 4])
    #expect(s.chips.totalEarned == 14 && s.health.ok)
}

@Test func decodesFirstWeekWithNullsAndEmptyLists() throws {
    let s = try Status.decode(fixture("status-first-week"))
    #expect(s.lastWeek == nil && s.history.isEmpty && s.chips.pending.isEmpty)
    #expect(s.checkin.steps.first?.links.isEmpty == true)
}

@Test func unknownColorFailsLoudly() throws {
    let text = String(decoding: try fixture("status-first-week"), as: UTF8.self)
        .replacingOccurrences(of: "\"color\": \"green\"", with: "\"color\": \"purple\"")
    #expect(throws: DecodingError.self) { try Status.decode(Data(text.utf8)) }
}
