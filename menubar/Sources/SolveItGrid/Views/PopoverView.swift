import AppKit
import SolveItGridCore
import SwiftUI

struct PopoverView: View {
    let model: AppModel
    let onHistory: () -> Void

    private var isMonday: Bool { Calendar.current.component(.weekday, from: Date()) == 2 }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let report = errorReport(failure: model.failure, status: model.status) {
                ErrorBannerView(report: report)
            }
            if let status = model.status {
                content(status)
            } else if model.failure == nil {
                Text("Loading…").foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(width: 340)
        .background(ActivePopoverMaterial())
    }

    @ViewBuilder
    private func content(_ status: Status) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text("This week's chips").font(.headline)
            Spacer()
            Text(Copy.weekRange(start: status.week.start, end: status.week.end))
                .font(.caption).foregroundStyle(.secondary)
        }
        ChipBoardView(board: chipBoard(for: status)) { Task { await model.ackAll() } }
        Label(Copy.redLine(status.redDone), systemImage: "circle.fill")
            .font(.caption)
            .foregroundStyle(.secondary)
            .labelStyle(RedDotLabelStyle())

        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text("Today's check-in").font(.headline)
                Spacer()
                Text(Copy.leftLine(status.checkin.steps.filter { !$0.done }.count))
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let line = Copy.lastWeekLine(status.lastWeek, isMonday: isMonday) {
                Text(line).font(.caption).foregroundStyle(.secondary)
            }
            CheckinListView(steps: status.checkin.steps) { step in Task { await model.tick(step) } }
        }

        HStack(spacing: 8) {
            Button { model.snooze() } label: { Text("Snooze 1 hour").frame(maxWidth: .infinity) }
            Button { Task { await model.checkinDone() } } label: { Text("Done for today").frame(maxWidth: .infinity) }
        }
        .controlSize(.large)

        Divider()
        HStack(spacing: 14) {
            Text(Copy.streakLine(status.streak.current))
            Text(Copy.chipsEarnedLine(status.chips.totalEarned))
            Spacer()
            Button("History", action: onHistory).buttonStyle(.link)
        }
        .font(.caption)
        .foregroundStyle(.secondary)
    }
}

/// The reds line gets a small red dot instead of a full-size icon.
private struct RedDotLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 6) {
            Circle().fill(Color(nsColor: .systemRed)).frame(width: 7, height: 7)
            configuration.title
        }
    }
}

/// The popover's material, pinned to its active look so it never flashes the lighter inactive state.
private struct ActivePopoverMaterial: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = .popover
        view.blendingMode = .behindWindow
        view.state = .active
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {}
}
