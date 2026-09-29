import Foundation

public struct CommandResult: Equatable, Sendable {
    public var exitCode: Int32
    public var stdout: Data
    public var stderr: String

    public init(exitCode: Int32, stdout: Data, stderr: String) {
        self.exitCode = exitCode
        self.stdout = stdout
        self.stderr = stderr
    }
}

public protocol CommandRunner: Sendable {
    func run(_ executable: URL, _ arguments: [String], timeout: TimeInterval) async throws -> CommandResult
}

/// Guarantees a continuation is resumed exactly once when two paths race (exit vs. timeout).
private final class Once: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false

    func run(_ body: () -> Void) {
        lock.lock()
        defer { lock.unlock() }
        guard !done else { return }
        done = true
        body()
    }
}

/// Runs a process off the main thread, terminating it when it outlives `timeout`.
public struct ProcessRunner: CommandRunner {
    public init() {}

    public func run(_ executable: URL, _ arguments: [String], timeout: TimeInterval) async throws -> CommandResult {
        try await withCheckedThrowingContinuation { continuation in
            let process = Process()
            process.executableURL = executable
            process.arguments = arguments
            let out = Pipe()
            let err = Pipe()
            process.standardOutput = out
            process.standardError = err
            let once = Once()
            do {
                try process.run()
            } catch {
                continuation.resume(throwing: CLIError.failed(exitCode: -1, stderr: error.localizedDescription))
                return
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeout) {
                guard process.isRunning else { return }
                process.terminate()
                once.run { continuation.resume(throwing: CLIError.timedOut(seconds: timeout)) }
            }
            DispatchQueue.global().async {
                // Drain both pipes concurrently so a chatty process can't block on a full pipe.
                var stdout = Data()
                var stderr = Data()
                let group = DispatchGroup()
                DispatchQueue.global().async(group: group) { stdout = out.fileHandleForReading.readDataToEndOfFile() }
                DispatchQueue.global().async(group: group) { stderr = err.fileHandleForReading.readDataToEndOfFile() }
                group.wait()
                process.waitUntilExit()
                once.run {
                    continuation.resume(returning: CommandResult(
                        exitCode: process.terminationStatus, stdout: stdout,
                        stderr: String(decoding: stderr, as: UTF8.self)))
                }
            }
        }
    }
}

/// Talks to the `solve-it-grid` CLI. The app never reads Things or the state database itself.
public struct CLIClient: Sendable {
    public let executable: URL
    private let runner: CommandRunner
    private let timeout: TimeInterval

    public init(executable: URL, runner: CommandRunner = ProcessRunner(), timeout: TimeInterval = 10) {
        self.executable = executable
        self.runner = runner
        self.timeout = timeout
    }

    /// The `cliPath` user default, or `~/.local/bin/solve-it-grid`.
    public static func defaultExecutable(defaults: UserDefaults = .standard) -> URL {
        executable(cliPath: defaults.string(forKey: "cliPath"))
    }

    /// `cliPath` with `~` expanded, or `~/.local/bin/solve-it-grid` when unset.
    public static func executable(cliPath: String?) -> URL {
        if let cliPath, !cliPath.isEmpty {
            return URL(fileURLWithPath: NSString(string: cliPath).expandingTildeInPath)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/bin/solve-it-grid")
    }

    public func status() async throws -> Status {
        let result = try await invoke(["status", "--json"])
        do {
            return try Status.decode(result.stdout)
        } catch {
            throw CLIError.decoding(String(describing: error))
        }
    }

    public func ackChips(_ ids: [Int]) async throws {
        guard !ids.isEmpty else { return }
        _ = try await invoke(["chip", "ack"] + ids.map(String.init))
    }

    public func checkinDone() async throws {
        _ = try await invoke(["checkin", "done"])
    }

    public func tick(_ step: String) async throws {
        _ = try await invoke(["checkin", "tick", step])
    }

    private func invoke(_ arguments: [String]) async throws -> CommandResult {
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw CLIError.notFound(path: executable.path)
        }
        let result = try await runner.run(executable, arguments, timeout: timeout)
        guard result.exitCode == 0 else {
            throw CLIError.failed(exitCode: result.exitCode,
                                  stderr: result.stderr.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return result
    }
}
