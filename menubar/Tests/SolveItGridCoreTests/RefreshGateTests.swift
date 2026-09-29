import Foundation
import Testing
@testable import SolveItGridCore

actor Counter {
    var runs = 0
    func bump() { runs += 1 }
}

@Test func requestDuringRunIsCoalescedIntoOneMoreRun() async {
    let gate = RefreshGate()
    let counter = Counter()
    let first = Task {
        await gate.run {
            await counter.bump()
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
    }
    try? await Task.sleep(nanoseconds: 50_000_000)
    // Two requests while the first is still running: both fold into one follow-up run.
    await gate.run { await counter.bump() }
    await gate.run { await counter.bump() }
    await first.value
    #expect(await counter.runs == 2)
}

@Test func idleGateRunsImmediately() async {
    let gate = RefreshGate()
    let counter = Counter()
    await gate.run { await counter.bump() }
    await gate.run { await counter.bump() }
    #expect(await counter.runs == 2)
}
