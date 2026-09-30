import Foundation

/// Runs `executable` as a child sharing this process's stdin, stdout and stderr, waits for it, and
/// returns the status to exit with. SIGTERM and SIGINT are passed on to the child.
///
/// The launchd agent runs the CLI this way (`SolveItGrid --categorize`). As a plain child of the app's
/// executable, the CLI's reads of the Things database are attributed to Solve It Grid rather than to
/// the Python interpreter, so macOS asks about the app once instead of about Python on every run.
public func runAsChild(_ executable: URL, _ arguments: [String]) -> Int32 {
    let process = Process()
    process.executableURL = executable
    process.arguments = arguments
    do {
        try process.run()
    } catch {
        FileHandle.standardError.write(Data("Cannot run \(executable.path): \(error.localizedDescription)\n".utf8))
        return 127
    }
    // Ignore the signals only after spawning: an ignored signal stays ignored in the child.
    let pid = process.processIdentifier
    let signals = [SIGTERM, SIGINT]
    let forwarders = signals.map { sig -> DispatchSourceSignal in
        signal(sig, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: sig, queue: .global())
        source.setEventHandler { kill(pid, sig) }
        source.resume()
        return source
    }
    process.waitUntilExit()
    forwarders.forEach { $0.cancel() }
    signals.forEach { signal($0, SIG_DFL) }
    if process.terminationReason == .uncaughtSignal {
        return 128 + process.terminationStatus
    }
    return process.terminationStatus
}
