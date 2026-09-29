import Foundation

/// Serializes refreshes without dropping any: a request that arrives mid-refresh is folded into
/// exactly one more pass, so the state read after an action is always fresh.
public actor RefreshGate {
    private var running = false
    private var again = false

    public init() {}

    public func run(_ body: @Sendable () async -> Void) async {
        if running {
            again = true
            return
        }
        running = true
        repeat {
            again = false
            await body()
        } while again
        running = false
    }
}
