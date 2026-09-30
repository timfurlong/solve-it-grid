import Foundation
import Testing
@testable import SolveItGridCore

private let sh = URL(fileURLWithPath: "/bin/sh")

@Test func childExitStatusPassesThrough() {
    #expect(runAsChild(sh, ["-c", "exit 3"]) == 3)
}

@Test func childKilledBySignalExitsWith128PlusSignal() {
    #expect(runAsChild(sh, ["-c", "kill -TERM $$"]) == 128 + SIGTERM)
}

@Test func missingExecutableExits127() {
    #expect(runAsChild(URL(fileURLWithPath: "/nonexistent/solve-it-grid"), ["categorize"]) == 127)
}
