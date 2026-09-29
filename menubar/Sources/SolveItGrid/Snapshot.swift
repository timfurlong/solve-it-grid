import AppKit
import SolveItGridCore
import SwiftUI

/// `SolveItGrid --snapshot <dir> [--status <file.json>]` renders the popover and history window to PNGs
/// (light and dark) and quits. It uses live status, or the given status JSON. Used to check layout
/// without screen-recording permission.
enum Snapshot {
    static func requestedDirectory(_ arguments: [String] = CommandLine.arguments) -> URL? {
        guard let i = arguments.firstIndex(of: "--snapshot"), i + 1 < arguments.count else { return nil }
        return URL(fileURLWithPath: arguments[i + 1], isDirectory: true)
    }

    static func statusFile(_ arguments: [String] = CommandLine.arguments) -> URL? {
        guard let i = arguments.firstIndex(of: "--status"), i + 1 < arguments.count else { return nil }
        return URL(fileURLWithPath: arguments[i + 1])
    }

    @MainActor
    static func run(model: AppModel, into directory: URL) async {
        if let file = statusFile(), let data = try? Data(contentsOf: file), let status = try? Status.decode(data) {
            model.show(status)
        } else {
            await model.refresh()
        }
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        for (name, appearance) in [("light", NSAppearance.Name.aqua), ("dark", .darkAqua)] {
            write(PopoverView(model: model, onHistory: {}), appearance, directory.appendingPathComponent("popover-\(name).png"))
            write(HistoryView(model: model), appearance, directory.appendingPathComponent("history-\(name).png"))
        }
        NSApp.terminate(nil)
    }

    @MainActor
    private static func write<V: View>(_ view: V, _ appearance: NSAppearance.Name, _ url: URL) {
        // The popover supplies its own background on screen; give the snapshot one explicitly.
        let host = NSHostingView(rootView: view.background(Color(nsColor: .windowBackgroundColor)))
        host.appearance = NSAppearance(named: appearance)
        let size = host.fittingSize
        let window = NSWindow(contentRect: NSRect(origin: .zero, size: size), styleMask: .borderless,
                              backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: appearance)
        window.backgroundColor = appearance == .darkAqua ? NSColor(white: 0.16, alpha: 1) : NSColor(white: 0.96, alpha: 1)
        window.contentView = host
        host.frame = NSRect(origin: .zero, size: size)
        host.layoutSubtreeIfNeeded()
        guard let rep = window.contentView?.bitmapImageRepForCachingDisplay(in: host.bounds) else { return }
        window.contentView?.cacheDisplay(in: host.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }
}
