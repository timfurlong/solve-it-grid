import AppKit
import SolveItGridCore
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = AppModel()
    private var statusItem: NSStatusItem!
    private var pollTimer: Timer?
    private var pulseTimer: Timer?
    private var pulseOn = true
    private let popover = NSPopover()
    private var historyWindow: NSWindow?
    private let poster = NotificationPoster()

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let directory = Snapshot.requestedDirectory() {
            Task { await Snapshot.run(model: model, into: directory) }
            return
        }
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.target = self
        statusItem.button?.action = #selector(statusItemClicked)
        model.onChange = { [weak self] in self?.redraw() }
        redraw()

        let content = NSHostingController(rootView: PopoverView(model: model) { [weak self] in self?.showHistory() })
        content.sizingOptions = .preferredContentSize
        popover.contentViewController = content
        popover.behavior = .transient

        poster.configure()
        poster.onOpen = { [weak self] in self?.showPopover() }
        poster.onSnooze = { [weak self] in self?.model.snooze() }
        model.onNotify = { [weak self] notifications in notifications.forEach { self?.poster.post($0) } }
        model.onSync = { [weak self] active in self?.poster.withdraw(keeping: active) }
        poster.requestAuthorization()
        LoginItem.registerIfNeeded()

        pollTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.model.refresh() }
        }
        NSWorkspace.shared.notificationCenter.addObserver(
            self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        Task { await model.refresh() }
    }

    @objc private func didWake() {
        Task { await model.refresh() }
    }

    @objc private func statusItemClicked() {
        if popover.isShown {
            popover.performClose(nil)
        } else {
            showPopover()
        }
    }

    /// Opens the popover under the status item and refreshes it. Notification actions call this too.
    func showPopover() {
        guard let button = statusItem.button else { return }
        Task { await model.refresh() }
        // A menu-bar-only app must be activated forcefully, or the popover draws its inactive
        // (lighter) material until clicked. The newer cooperative activate() doesn't do this.
        NSApp.activate(ignoringOtherApps: true)
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        popover.contentViewController?.view.window?.makeKey()
    }

    func showHistory() {
        if historyWindow == nil {
            let window = NSWindow(contentViewController: NSHostingController(rootView: HistoryView(model: model)))
            window.title = "Solve It Grid History"
            window.styleMask = [.titled, .closable]
            window.isReleasedWhenClosed = false
            historyWindow = window
        }
        popover.performClose(nil)
        historyWindow?.center()
        historyWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate()
    }

    private func redraw() {
        let state = model.icon
        statusItem.button?.image = StatusIconRenderer.image(for: state, pulseOn: pulseOn)
        statusItem.button?.setAccessibilityLabel(iconAccessibilityLabel(state))
        updatePulse(for: state)
    }

    /// Pulses the center dot while a chip waits, unless Reduce Motion is on.
    private func updatePulse(for state: IconState) {
        var waiting = false
        if case .ring(_, .chipWaiting) = state { waiting = true }
        let reduceMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        if waiting && !reduceMotion {
            guard pulseTimer == nil else { return }
            pulseTimer = Timer.scheduledTimer(withTimeInterval: 0.8, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    guard let self else { return }
                    self.pulseOn.toggle()
                    self.statusItem.button?.image = StatusIconRenderer.image(for: self.model.icon, pulseOn: self.pulseOn)
                }
            }
        } else {
            pulseTimer?.invalidate()
            pulseTimer = nil
            pulseOn = true
        }
    }
}
