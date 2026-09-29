import AppKit
import SolveItGridCore

extension GridColor {
    var nsColor: NSColor {
        switch self {
        case .red: return .systemRed
        case .yellow: return .systemYellow
        case .green: return .systemGreen
        case .blue: return .systemBlue
        case .unscored: return .systemGray
        }
    }
}

/// Draws the menu bar ring. Drawing happens in the image's handler, so dynamic colors
/// (labelColor) follow light and dark mode.
enum StatusIconRenderer {
    private static let size = NSSize(width: 18, height: 18)
    private static let radius: CGFloat = 6.2
    private static let gapDegrees: CGFloat = 12

    static func image(for state: IconState, pulseOn: Bool) -> NSImage {
        switch state {
        case .error:
            let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
                .applying(NSImage.SymbolConfiguration(hierarchicalColor: .systemRed))
            let symbol = NSImage(systemSymbolName: "exclamationmark.triangle.fill",
                                 accessibilityDescription: "Solve It Grid needs attention")?
                .withSymbolConfiguration(config) ?? NSImage()
            symbol.isTemplate = false
            return symbol
        case let .ring(segments, center):
            let image = NSImage(size: size, flipped: false) { rect in
                drawRing(segments, in: rect)
                drawCenter(center, pulseOn: pulseOn, in: rect)
                return true
            }
            image.isTemplate = false
            return image
        }
    }

    private static func drawRing(_ segments: [Segment], in rect: NSRect) {
        guard !segments.isEmpty else { return }
        let middle = NSPoint(x: rect.midX, y: rect.midY)
        let span = 360 / CGFloat(segments.count)
        // Clockwise from 6 o'clock, so the yellows (listed first) land on the left and the greens
        // on the right, like the grid's not-fun and fun columns: work bottom-left, home top-left.
        for (i, segment) in segments.enumerated() {
            let start = 270 - CGFloat(i) * span - gapDegrees / 2
            let end = start - (span - gapDegrees)
            let path = NSBezierPath()
            path.appendArc(withCenter: middle, radius: radius, startAngle: start, endAngle: end, clockwise: true)
            path.lineCapStyle = .round
            if segment.done {
                segment.color.nsColor.setStroke()
                path.lineWidth = 2.6
            } else {
                NSColor.labelColor.withAlphaComponent(0.3).setStroke()
                path.lineWidth = 2.0
            }
            path.stroke()
        }
    }

    private static func drawCenter(_ center: Center, pulseOn: Bool, in rect: NSRect) {
        let middle = NSPoint(x: rect.midX, y: rect.midY)
        func dot(_ r: CGFloat, _ color: NSColor) {
            color.setFill()
            NSBezierPath(ovalIn: NSRect(x: middle.x - r, y: middle.y - r, width: r * 2, height: r * 2)).fill()
        }
        switch center {
        case .none:
            break
        case .checkinDue:
            dot(2.3, .systemOrange)
        case let .chipWaiting(color):
            dot(2.4, color.nsColor.withAlphaComponent(pulseOn ? 1 : 0.35))
        case .weekHit:
            let check = NSBezierPath()
            check.move(to: NSPoint(x: middle.x - 2.4, y: middle.y))
            check.line(to: NSPoint(x: middle.x - 0.8, y: middle.y - 1.6))
            check.line(to: NSPoint(x: middle.x + 2.4, y: middle.y + 1.8))
            check.lineWidth = 1.4
            check.lineCapStyle = .round
            check.lineJoinStyle = .round
            NSColor.labelColor.setStroke()
            check.stroke()
        }
    }
}
