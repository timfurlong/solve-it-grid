import Foundation

public enum SlotState: Equatable, Sendable {
    case earned
    case pending(chipID: Int)
    case open

    public var caption: String {
        switch self {
        case .earned: return "In the jar"
        case .pending: return "Move it now"
        case .open: return "Not yet"
        }
    }
}

/// One of this week's units, drawn as a poker chip.
public struct ChipSlot: Equatable, Sendable {
    public var unitID: String
    public var label: String
    public var color: GridColor
    public var state: SlotState
}

/// A chip from an earlier week that still hasn't been moved to the jar.
public struct LeftoverChip: Equatable, Sendable {
    public var chip: Chip
    public var label: String
}

public struct ChipBoard: Equatable, Sendable {
    public var slots: [ChipSlot]
    public var leftovers: [LeftoverChip]
    public var pendingIDs: [Int]
    public var ackLabel: String?
}

public func chipBoard(for status: Status) -> ChipBoard {
    let pending = status.chips.pending
    let thisWeek = pending.filter { $0.weekStart == status.week.start }
    let slots = status.units.map { unit -> ChipSlot in
        let state: SlotState
        if let chip = thisWeek.first(where: { $0.unit == unit.id }) {
            state = .pending(chipID: chip.id)
        } else {
            state = unit.done ? .earned : .open
        }
        return ChipSlot(unitID: unit.id, label: unit.label, color: unit.color, state: state)
    }
    let labels = Dictionary(status.units.map { ($0.id, $0.label) }, uniquingKeysWith: { first, _ in first })
    let leftovers = pending
        .filter { $0.weekStart != status.week.start }
        .map { LeftoverChip(chip: $0, label: labels[$0.unit] ?? $0.unit) }
    let ackLabel: String?
    switch pending.count {
    case 0: ackLabel = nil
    case 1: ackLabel = "I moved the \(pending[0].color.rawValue) chip"
    default: ackLabel = "I moved \(pending.count) chips"
    }
    return ChipBoard(slots: slots, leftovers: leftovers, pendingIDs: pending.map(\.id), ackLabel: ackLabel)
}

/// The letter printed on a chip: W and H for the work and home yellows, otherwise the label's initial.
public func chipLetter(for slot: ChipSlot) -> String {
    if slot.unitID.contains("work") { return "W" }
    if slot.unitID.contains("home") { return "H" }
    return slot.label.first.map { String($0).uppercased() } ?? "?"
}
