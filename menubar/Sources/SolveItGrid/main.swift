import AppKit

// Top-level code runs on the main thread; say so, so the main-actor delegate can be created here.
MainActor.assumeIsolated {
    let app = NSApplication.shared
    let delegate = AppDelegate()  // held for the app's lifetime: run() blocks until quit
    app.delegate = delegate
    app.setActivationPolicy(.accessory)
    app.run()
}
