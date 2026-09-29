import Foundation
import Testing
@testable import SolveItGridCore

final class FakeRunner: CommandRunner, @unchecked Sendable {
    var calls: [[String]] = []
    var result: CommandResult

    init(_ result: CommandResult = CommandResult(exitCode: 0, stdout: Data(), stderr: "")) {
        self.result = result
    }

    func run(_ executable: URL, _ arguments: [String], timeout: TimeInterval) async throws -> CommandResult {
        calls.append(arguments)
        return result
    }
}

private let existing = URL(fileURLWithPath: "/bin/echo")  // any executable; FakeRunner never runs it

@Test func statusArgumentsAndDecode() async throws {
    let runner = FakeRunner(CommandResult(exitCode: 0, stdout: try fixture("status-thursday"), stderr: ""))
    let status = try await CLIClient(executable: existing, runner: runner).status()
    #expect(runner.calls == [["status", "--json"]])
    #expect(status.redDone == 3)
}

@Test func ackArgumentsAndEmptyIsNoop() async throws {
    let runner = FakeRunner()
    let client = CLIClient(executable: existing, runner: runner)
    try await client.ackChips([])
    try await client.ackChips([57, 61])
    #expect(runner.calls == [["chip", "ack", "57", "61"]])
}

@Test func checkinArguments() async throws {
    let runner = FakeRunner()
    let client = CLIClient(executable: existing, runner: runner)
    try await client.checkinDone()
    try await client.tick("colors-reviewed")
    #expect(runner.calls == [["checkin", "done"], ["checkin", "tick", "colors-reviewed"]])
}

@Test func nonZeroExitThrowsFailedWithStderr() async {
    let runner = FakeRunner(CommandResult(exitCode: 1, stdout: Data(), stderr: "boom\nCannot read the Things database\n"))
    await #expect(throws: CLIError.failed(exitCode: 1, stderr: "boom\nCannot read the Things database")) {
        try await CLIClient(executable: existing, runner: runner).status()
    }
}

@Test func badJSONThrowsDecoding() async {
    let runner = FakeRunner(CommandResult(exitCode: 0, stdout: Data("nope".utf8), stderr: ""))
    do {
        _ = try await CLIClient(executable: existing, runner: runner).status()
        Issue.record("expected a decoding error")
    } catch let error as CLIError {
        guard case .decoding = error else { Issue.record("wrong error \(error)"); return }
    } catch {
        Issue.record("unexpected \(error)")
    }
}

@Test func missingExecutableThrowsNotFound() async {
    let runner = FakeRunner()
    await #expect(throws: CLIError.notFound(path: "/nonexistent/solve-it-grid")) {
        try await CLIClient(executable: URL(fileURLWithPath: "/nonexistent/solve-it-grid"), runner: runner).status()
    }
    #expect(runner.calls.isEmpty)
}

@Test func executableHonorsCliPath() {
    #expect(CLIClient.executable(cliPath: nil).path.hasSuffix("/.local/bin/solve-it-grid"))
    #expect(CLIClient.executable(cliPath: "").path.hasSuffix("/.local/bin/solve-it-grid"))
    #expect(CLIClient.executable(cliPath: "~/bin/custom-cli").path
            == NSString(string: "~/bin/custom-cli").expandingTildeInPath)
}

@Test func processRunnerCapturesOutput() async throws {
    let r = try await ProcessRunner().run(URL(fileURLWithPath: "/bin/echo"), ["hi"], timeout: 5)
    #expect(r.exitCode == 0 && r.stdout == Data("hi\n".utf8))
}

@Test func processRunnerTimesOut() async {
    let start = Date()
    await #expect(throws: CLIError.timedOut(seconds: 0.5)) {
        _ = try await ProcessRunner().run(URL(fileURLWithPath: "/bin/sleep"), ["5"], timeout: 0.5)
    }
    #expect(Date().timeIntervalSince(start) < 2)
}
