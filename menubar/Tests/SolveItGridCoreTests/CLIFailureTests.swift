import Foundation
import Testing
@testable import SolveItGridCore

private let t0 = Date(timeIntervalSince1970: 1_790_000_000)

@Test func nextKeepsSinceAndCounts() {
    let first = CLIFailure.next(.timedOut(seconds: 10), after: nil, now: t0)
    #expect(first == CLIFailure(error: .timedOut(seconds: 10), since: t0, count: 1))
    let second = CLIFailure.next(.failed(exitCode: 1, stderr: "x"), after: first, now: t0.addingTimeInterval(60))
    #expect(second == CLIFailure(error: .failed(exitCode: 1, stderr: "x"), since: t0, count: 2))
}

@Test func loneTimeoutIsHidden() {
    #expect(!CLIFailure(error: .timedOut(seconds: 10), since: t0, count: 1).isShown)
    #expect(CLIFailure(error: .timedOut(seconds: 10), since: t0, count: 2).isShown)
}

@Test func otherFailuresShowAtOnce() {
    for error: CLIError in [.notFound(path: "/x"), .failed(exitCode: 1, stderr: "x"), .decoding("x")] {
        #expect(CLIFailure(error: error, since: t0, count: 1).isShown)
    }
}
