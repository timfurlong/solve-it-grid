// Draws the app icon (a poker chip whose face is the Solve It Grid) and writes an .iconset.
// Usage (from menubar/): swift scripts/make-icon.swift /tmp/AppIcon.iconset &&
//   iconutil -c icns /tmp/AppIcon.iconset -o Bundle/AppIcon.icns
import AppKit

let output = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "AppIcon.iconset")
try? FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

func color(_ hex: UInt32) -> NSColor {
    NSColor(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
}

/// Draws in a 1024-point space; the caller scales the context.
func drawIcon() {
    let full = NSRect(x: 0, y: 0, width: 1024, height: 1024)
    // Full-bleed background; macOS applies its own rounded mask.
    NSGradient(starting: color(0x34363D), ending: color(0x16171A))!.draw(in: full, angle: -90)

    let center = NSPoint(x: 512, y: 512)
    let radius: CGFloat = 350

    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.45)
    shadow.shadowBlurRadius = 40
    shadow.shadowOffset = NSSize(width: 0, height: -18)
    shadow.set()
    NSColor.black.setFill()
    NSBezierPath(ovalIn: NSRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2)).fill()
    NSGraphicsContext.restoreGraphicsState()

    // The grid's quadrants: not fun on the left, fun on the right, stimulating on top.
    let quadrants: [(start: CGFloat, color: UInt32)] = [
        (90, 0xFF3B30),   // top-left: red (fires)
        (0, 0x34C759),    // top-right: green (fueling fun)
        (180, 0xFFCC00),  // bottom-left: yellow (shoulds and oughts)
        (270, 0x0A84FF),  // bottom-right: blue (passive fun)
    ]
    for q in quadrants {
        let wedge = NSBezierPath()
        wedge.move(to: center)
        wedge.appendArc(withCenter: center, radius: radius, startAngle: q.start, endAngle: q.start + 90)
        wedge.close()
        color(q.color).setFill()
        wedge.fill()
    }

    // White edge inserts, like a real chip.
    let insertRadius: CGFloat = 310
    let segment = 2 * .pi * insertRadius / 16
    let inserts = NSBezierPath(ovalIn: NSRect(x: center.x - insertRadius, y: center.y - insertRadius,
                                              width: insertRadius * 2, height: insertRadius * 2))
    inserts.lineWidth = 64
    inserts.setLineDash([segment, segment], count: 2, phase: segment / 2)
    NSColor.white.withAlphaComponent(0.95).setStroke()
    inserts.stroke()

    // Dashed inner ring.
    let innerRadius: CGFloat = 210
    let inner = NSBezierPath(ovalIn: NSRect(x: center.x - innerRadius, y: center.y - innerRadius,
                                            width: innerRadius * 2, height: innerRadius * 2))
    inner.lineWidth = 12
    inner.setLineDash([28, 22], count: 2, phase: 0)
    NSColor.white.withAlphaComponent(0.85).setStroke()
    inner.stroke()

    // Crisp rim.
    let rim = NSBezierPath(ovalIn: NSRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2))
    rim.lineWidth = 8
    NSColor.black.withAlphaComponent(0.25).setStroke()
    rim.stroke()
}

let sizes: [(name: String, pixels: Int)] = [
    ("icon_16x16", 16), ("icon_16x16@2x", 32), ("icon_32x32", 32), ("icon_32x32@2x", 64),
    ("icon_128x128", 128), ("icon_128x128@2x", 256), ("icon_256x256", 256), ("icon_256x256@2x", 512),
    ("icon_512x512", 512), ("icon_512x512@2x", 1024),
]
for (name, pixels) in sizes {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels, bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                               bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let scale = CGFloat(pixels) / 1024
    NSGraphicsContext.current?.cgContext.scaleBy(x: scale, y: scale)
    drawIcon()
    NSGraphicsContext.restoreGraphicsState()
    try rep.representation(using: .png, properties: [:])!.write(to: output.appendingPathComponent("\(name).png"))
}
print("Wrote \(output.path)")
