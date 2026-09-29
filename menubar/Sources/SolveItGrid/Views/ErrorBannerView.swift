import SolveItGridCore
import SwiftUI

struct ErrorBannerView: View {
    let report: ErrorReport

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label(report.title, systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .foregroundStyle(.red)
            Text(report.detail).font(.callout).textSelection(.enabled)
            if let fix = report.fix {
                Text(fix).font(.callout).fontWeight(.medium).textSelection(.enabled)
            }
            if let since = report.since {
                Text(Copy.sinceLine(since)).font(.caption).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color.red.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.red.opacity(0.5), lineWidth: 1))
    }
}
