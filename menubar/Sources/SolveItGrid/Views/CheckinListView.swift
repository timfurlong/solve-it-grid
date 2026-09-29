import AppKit
import SolveItGridCore
import SwiftUI

struct CheckinListView: View {
    let steps: [Step]
    let onTick: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(steps, id: \.id) { step in
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 8) {
                        indicator(for: step)
                        Text(step.label).foregroundStyle(step.done ? .secondary : .primary)
                        Spacer()
                        if !step.done, inlineLink(step) != nil {
                            linkButton(inlineLink(step)!)
                        }
                    }
                    if !step.done, inlineLink(step) == nil, !step.links.isEmpty {
                        let capped = visibleLinks(step.links)
                        ForEach(capped.shown, id: \.url) { link in
                            linkButton(link).padding(.leading, 26)
                        }
                        if capped.hiddenCount > 0 {
                            Text(Copy.moreLine(capped.hiddenCount))
                                .font(.callout).foregroundStyle(.secondary).padding(.leading, 26)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func indicator(for step: Step) -> some View {
        if step.manual {
            Button {
                if !step.done { onTick(step.id) }
            } label: {
                Image(systemName: step.done ? "checkmark.square.fill" : "square")
            }
            .buttonStyle(.plain)
            .disabled(step.done)
            .accessibilityLabel(step.done ? "\(step.label), done" : "Mark \(step.label)")
        } else {
            Image(systemName: step.done ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(.secondary)
                .accessibilityHidden(true)
        }
    }

    /// A single generic "Show" link sits at the end of the row; per-item links list underneath.
    private func inlineLink(_ step: Step) -> SolveItGridCore.Link? {
        step.links.count == 1 && step.links[0].label == "Show" ? step.links[0] : nil
    }

    private func linkButton(_ link: SolveItGridCore.Link) -> some View {
        Button(link.label) {
            if let url = URL(string: link.url) { NSWorkspace.shared.open(url) }
        }
        .buttonStyle(.link)
        .font(.callout)
    }
}
