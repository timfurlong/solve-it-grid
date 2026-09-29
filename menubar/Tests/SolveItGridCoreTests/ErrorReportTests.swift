import Foundation
import Testing
@testable import SolveItGridCore

private let t0 = Date(timeIntervalSince1970: 1_790_000_000)
private func failing(_ e: CLIError) -> CLIFailure { CLIFailure(error: e, since: t0) }
private func healthy() throws -> Status { try Status.decode(fixture("status-thursday")) }

@Test func notFoundReport() {
    let r = errorReport(failure: failing(.notFound(path: "/x/solve-it-grid")), status: nil)
    #expect(r == ErrorReport(title: "solve-it-grid not found", detail: "/x/solve-it-grid",
                             fix: "Install it from the repo: uv tool install --editable ./engine",
                             since: ISO8601DateFormatter().string(from: t0)))
}

@Test func timedOutReport() {
    let r = errorReport(failure: failing(.timedOut(seconds: 10)), status: nil)
    #expect(r?.title == "solve-it-grid status timed out" && r?.detail == "No answer after 10 seconds.")
    #expect(r?.fix == "Check that Things is running.")
}

@Test func failedReportUsesLastStderrLine() {
    let r = errorReport(failure: failing(.failed(exitCode: 1, stderr: "trace\nCannot read the Things database.\n\n")),
                        status: nil)
    #expect(r?.title == "solve-it-grid status failed" && r?.detail == "Cannot read the Things database.")
    #expect(r?.fix == nil)
}

@Test func decodingReport() {
    let r = errorReport(failure: failing(.decoding("keyNotFound units")), status: nil)
    #expect(r?.title == "Unexpected status output" && r?.detail == "keyNotFound units")
    #expect(r?.fix == "Rebuild the app after updating the CLI.")
}

@Test func failureBeatsHealthErrors() throws {
    var s = try healthy()
    s.health = Health(ok: false, errors: [HealthError(source: "setup", message: "Missing tags", since: nil)])
    #expect(errorReport(failure: failing(.timedOut(seconds: 10)), status: s)?.title == "solve-it-grid status timed out")
}

@Test func setupHealthReport() throws {
    var s = try healthy()
    s.health = Health(ok: false, errors: [
        HealthError(source: "categorizer", message: "First review pending.", since: nil),
        HealthError(source: "setup", message: "Things area 'Work' not found.", since: nil),
    ])
    let r = errorReport(failure: nil, status: s)
    #expect(r == ErrorReport(title: "Setup needs attention",
                             detail: "First review pending.\nThings area 'Work' not found.", fix: nil, since: nil))
}

@Test func loggedInHint() throws {
    var s = try healthy()
    s.health = Health(ok: false, errors: [
        HealthError(source: "categorizer", message: "Not logged in · Please run /login", since: "2026-10-01T09:00:00-06:00"),
    ])
    let r = errorReport(failure: nil, status: s)
    #expect(r?.title == "Categorizer needs attention" && r?.since == "2026-10-01T09:00:00-06:00")
    #expect(r?.fix == "Claude Code is not logged in: run `claude` in a terminal.")
}

@Test func nilWhenHealthy() throws {
    #expect(errorReport(failure: nil, status: try healthy()) == nil)
    #expect(errorReport(failure: nil, status: nil) == nil)
}
