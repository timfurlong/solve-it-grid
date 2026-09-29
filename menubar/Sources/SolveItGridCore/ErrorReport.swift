import Foundation

/// What the error banner and the error notification say.
public struct ErrorReport: Equatable, Sendable {
    public var title: String
    public var detail: String
    public var fix: String?
    public var since: String?

    public init(title: String, detail: String, fix: String?, since: String?) {
        self.title = title
        self.detail = detail
        self.fix = fix
        self.since = since
    }
}

/// A CLI failure takes precedence over health errors. Nil when everything is fine.
public func errorReport(failure: CLIFailure?, status: Status?) -> ErrorReport? {
    if let failure {
        let since = ISO8601DateFormatter().string(from: failure.since)
        switch failure.error {
        case let .notFound(path):
            return ErrorReport(title: "solve-it-grid not found", detail: path,
                               fix: "Install it from the repo: uv tool install --editable ./engine", since: since)
        case let .timedOut(seconds):
            return ErrorReport(title: "solve-it-grid status timed out",
                               detail: "No answer after \(Int(seconds)) seconds.",
                               fix: "Run solve-it-grid status in a terminal to see if it hangs.", since: since)
        case let .failed(exitCode, stderr):
            let lastLine = stderr.split(whereSeparator: \.isNewline)
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .last(where: { !$0.isEmpty })
            return ErrorReport(title: "solve-it-grid status failed", detail: lastLine ?? "Exit code \(exitCode).",
                               fix: nil, since: since)
        case let .decoding(message):
            return ErrorReport(title: "Unexpected status output", detail: message,
                               fix: "Rebuild the app after updating the CLI.", since: since)
        }
    }
    guard let status, !status.health.ok, !status.health.errors.isEmpty else { return nil }
    let errors = status.health.errors
    let title = errors.contains { $0.source == "setup" } ? "Setup needs attention" : "Categorizer needs attention"
    let loggedOut = errors.contains { $0.message.range(of: "logged in", options: .caseInsensitive) != nil }
    return ErrorReport(
        title: title,
        detail: errors.map(\.message).joined(separator: "\n"),
        fix: loggedOut ? "Claude Code is not logged in: run `claude` in a terminal." : nil,
        since: errors.compactMap(\.since).first)
}
