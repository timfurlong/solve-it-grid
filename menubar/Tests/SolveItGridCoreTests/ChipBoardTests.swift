import Testing
@testable import SolveItGridCore

private func thursday() throws -> Status { try Status.decode(fixture("status-thursday")) }

@Test func thursdayBoard() throws {
    let b = chipBoard(for: try thursday())
    #expect(b.slots.map(\.state) == [.earned, .pending(chipID: 57), .earned, .open])
    #expect(b.slots.map(\.state.caption) == ["In the jar", "Move it now", "In the jar", "Not yet"])
    #expect(b.slots.map(\.label) == ["Work yellow", "Home yellow", "Green", "Green"])
    #expect(b.ackLabel == "I moved the yellow chip" && b.leftovers.isEmpty && b.pendingIDs == [57])
}

@Test func mondayLeftoverFromLastWeekPlusNewChip() throws {
    var s = try thursday()
    s.week = Week(start: "2026-10-05", end: "2026-10-11", hit: false)
    s.units = s.units.map { Unit(id: $0.id, color: $0.color, label: $0.label, done: $0.id == "green-1") }
    s.chips.pending = [
        Chip(id: 57, weekStart: "2026-09-28", unit: "yellow-home", color: .yellow, awardedAt: "x"),
        Chip(id: 61, weekStart: "2026-10-05", unit: "green-1", color: .green, awardedAt: "y"),
    ]
    let b = chipBoard(for: s)
    #expect(b.slots.map(\.state) == [.open, .open, .pending(chipID: 61), .open])
    #expect(b.leftovers == [LeftoverChip(chip: s.chips.pending[0], label: "Home yellow")])
    #expect(b.pendingIDs == [57, 61])
    #expect(b.ackLabel == "I moved 2 chips")
}

@Test func noPendingNoAckLabel() throws {
    var s = try thursday()
    s.chips.pending = []
    let b = chipBoard(for: s)
    #expect(b.ackLabel == nil && b.pendingIDs.isEmpty)
    #expect(b.slots[1].state == .earned)
}

@Test func leftoverForUnknownUnitUsesItsID() throws {
    var s = try thursday()
    s.chips.pending = [Chip(id: 9, weekStart: "2026-09-14", unit: "old-goal", color: .green, awardedAt: "z")]
    #expect(chipBoard(for: s).leftovers.first?.label == "old-goal")
}

@Test func chipLetters() throws {
    let letters = chipBoard(for: try thursday()).slots.map(chipLetter(for:))
    #expect(letters == ["W", "H", "G", "G"])
    #expect(chipLetter(for: ChipSlot(unitID: "stretch", label: "stretch", color: .green, state: .open)) == "S")
}
