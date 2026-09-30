import AppKit
import SolveItGridCore

// The launchd agent starts this executable with --categorize: run one categorizer pass as a child,
// with no UI, so macOS attributes its reads of the Things database to this app (see runAsChild).
if CommandLine.arguments.dropFirst().first == "--categorize" {
    exit(runAsChild(CLIClient.defaultExecutable(), ["categorize"]))
}

// Top-level code runs on the main thread; say so, so the main-actor delegate can be created here.
MainActor.assumeIsolated {
    let app = NSApplication.shared
    let delegate = AppDelegate()  // held for the app's lifetime: run() blocks until quit
    app.delegate = delegate
    app.setActivationPolicy(.accessory)
    app.run()
}
