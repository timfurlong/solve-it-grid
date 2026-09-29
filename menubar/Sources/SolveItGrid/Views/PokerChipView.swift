import SolveItGridCore
import SwiftUI

/// A poker chip drawn like the physical ones: a solid disc, eight white edge inserts,
/// a dashed inner ring and the unit's letter. Open units are a dashed outline.
struct PokerChipView: View {
    let color: GridColor
    let letter: String
    let state: SlotState
    var size: CGFloat = 46

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var lifted = false

    private var tint: Color { Color(nsColor: color.nsColor) }
    private var isPending: Bool { if case .pending = state { return true } else { return false } }

    var body: some View {
        Group {
            if state == .open {
                Circle()
                    .inset(by: size * 0.045)
                    .stroke(tint, style: StrokeStyle(lineWidth: size * 0.04, dash: [size * 0.075, size * 0.06]))
            } else {
                chip
            }
        }
        .frame(width: size, height: size)
        .shadow(color: .black.opacity(isPending ? 0.28 : 0), radius: 6, y: 5)
        .offset(y: isPending && lifted ? -4 : 0)
        .onAppear {
            guard isPending, !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.3).repeatForever(autoreverses: true)) { lifted = true }
        }
        .accessibilityHidden(true)
    }

    private var chip: some View {
        let insertRadius = size * 0.4125
        let segment = 2 * .pi * insertRadius / 16
        return ZStack {
            Circle().fill(tint)
            Circle()
                .inset(by: size / 2 - insertRadius)
                .stroke(.white.opacity(0.92), style: StrokeStyle(lineWidth: size * 0.1, dash: [segment, segment]))
                .rotationEffect(.degrees(-11))
            Circle()
                .inset(by: size / 2 - size * 0.2875)
                .stroke(.white.opacity(0.75), style: StrokeStyle(lineWidth: max(1, size * 0.025),
                                                                   dash: [size * 0.04, size * 0.04]))
            Circle().stroke(.black.opacity(0.14), lineWidth: 1)
            Text(letter)
                .font(.system(size: size * 0.31, weight: .bold, design: .rounded))
                .foregroundStyle(.black.opacity(0.6))
        }
    }
}
