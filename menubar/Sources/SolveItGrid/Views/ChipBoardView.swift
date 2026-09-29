import SolveItGridCore
import SwiftUI

struct ChipBoardView: View {
    let board: ChipBoard
    let onAck: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 4) {
                ForEach(Array(board.slots.enumerated()), id: \.offset) { _, slot in
                    VStack(spacing: 6) {
                        PokerChipView(color: slot.color, letter: chipLetter(for: slot), state: slot.state)
                        Text(slot.label).font(.caption).fontWeight(.semibold).multilineTextAlignment(.center)
                        Text(slot.state.caption)
                            .font(.caption2)
                            .fontWeight(isPending(slot.state) ? .semibold : .regular)
                            .foregroundStyle(isPending(slot.state) ? .primary : .secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .accessibilityElement(children: .combine)
                }
            }
            ForEach(board.leftovers, id: \.chip.id) { leftover in
                HStack(spacing: 8) {
                    PokerChipView(color: leftover.chip.color, letter: String(leftover.label.prefix(1)),
                                  state: .pending(chipID: leftover.chip.id), size: 22)
                    Text("\(leftover.label), week of \(Copy.shortDate(leftover.chip.weekStart))").font(.caption)
                    Spacer()
                    Text(SlotState.pending(chipID: leftover.chip.id).caption).font(.caption).fontWeight(.semibold)
                }
            }
            if let ackLabel = board.ackLabel {
                Button(action: onAck) {
                    Text(ackLabel).frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
        }
    }

    private func isPending(_ state: SlotState) -> Bool {
        if case .pending = state { return true }
        return false
    }
}
