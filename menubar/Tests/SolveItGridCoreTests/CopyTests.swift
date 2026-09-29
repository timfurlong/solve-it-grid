import Foundation
import Testing
@testable import SolveItGridCore

@Test func redLine() {
    #expect(Copy.redLine(3) == "3 reds finished, not scored")
    #expect(Copy.redLine(1) == "1 red finished, not scored")
}

@Test func leftAndStreakLines() {
    #expect(Copy.leftLine(4) == "4 left")
    #expect(Copy.streakLine(3) == "3-week streak")
}

@Test func chipsEarnedLine() {
    #expect(Copy.chipsEarnedLine(14) == "14 chips earned")
    #expect(Copy.chipsEarnedLine(1) == "1 chip earned")
}

@Test func stepsLeftBody() {
    #expect(Copy.stepsLeftBody(4) == "4 steps left")
    #expect(Copy.stepsLeftBody(1) == "1 step left")
}

@Test func lastWeekLineOnlyOnMonday() {
    let hit = LastWeek(start: "2026-09-21", hit: true)
    #expect(Copy.lastWeekLine(hit, isMonday: false) == nil)
    #expect(Copy.lastWeekLine(nil, isMonday: true) == nil)
    #expect(Copy.lastWeekLine(hit, isMonday: true) == "Last week: hit")
    #expect(Copy.lastWeekLine(LastWeek(start: "2026-09-21", hit: false), isMonday: true) == "Last week: missed")
}

@Test func weekRangeAndShortDate() {
    #expect(Copy.weekRange(start: "2026-09-28", end: "2026-10-04") == "Sep 28 to Oct 4")
    #expect(Copy.shortDate("2026-09-21") == "Sep 21")
    #expect(Copy.shortDate("not a date") == "not a date")
}

@Test func sinceLineParsesPythonTimestamps() {
    let denver = TimeZone(identifier: "America/Denver")!
    #expect(Copy.sinceLine("2026-10-01T09:00:00-06:00", timeZone: denver) == "Since Oct 1, 9:00 AM")
    #expect(Copy.sinceLine("2026-10-01T09:00:00.123456-06:00", timeZone: denver) == "Since Oct 1, 9:00 AM")
    #expect(Copy.sinceLine("garbled", timeZone: denver) == "Since garbled")
}

@Test func visibleLinksCapsLongLists() {
    let links = (1...8).map { SolveItGridCore.Link(label: "Item \($0)", url: "things:///show?id=\($0)") }
    let capped = visibleLinks(links, limit: 5)
    #expect(capped.shown.map(\.label) == ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"])
    #expect(capped.hiddenCount == 3)
    #expect(Copy.moreLine(3) == "and 3 more")
    #expect(visibleLinks(Array(links.prefix(2)), limit: 5).hiddenCount == 0)
}
