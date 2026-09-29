import SolveItGridCore
import SwiftUI

struct HistoryView: View {
    let model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let status = model.status {
                HStack(spacing: 24) {
                    stat("Current streak", Copy.streakLine(status.streak.current))
                    stat("Best streak", Copy.streakLine(status.streak.best))
                }
                if status.history.isEmpty {
                    Text("No finished weeks yet.").foregroundStyle(.secondary)
                } else {
                    Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 6) {
                        GridRow {
                            Text("Week").fontWeight(.semibold)
                            Text("Units").fontWeight(.semibold)
                            Text("Result").fontWeight(.semibold)
                            Text("Chips").fontWeight(.semibold)
                        }
                        Divider().gridCellColumns(4)
                        ForEach(status.history.reversed(), id: \.start) { week in
                            GridRow {
                                Text(Copy.shortDate(week.start))
                                Text("\(week.unitsDone) of \(status.units.count)")
                                Text(week.hit ? "Hit" : "Missed").foregroundStyle(week.hit ? .green : .secondary)
                                Text("\(week.chips)")
                            }
                        }
                    }
                }
            } else {
                Text("Waiting for status…").foregroundStyle(.secondary)
            }
        }
        .padding(20)
        .frame(minWidth: 320, alignment: .topLeading)
    }

    private func stat(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title3).fontWeight(.semibold)
        }
    }
}
