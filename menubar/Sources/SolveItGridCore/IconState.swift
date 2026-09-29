import Foundation

/// Why the last `solve-it-grid` call failed.
public enum CLIError: Error, Equatable, Sendable {
    case notFound(path: String)
    case timedOut(seconds: Double)
    case failed(exitCode: Int32, stderr: String)
    case decoding(String)
}

/// A CLI failure and when the current run of failures began.
public struct CLIFailure: Equatable, Sendable {
    public var error: CLIError
    public var since: Date
    /// Failed polls in a row, counting this one.
    public var count: Int

    public init(error: CLIError, since: Date, count: Int = 1) {
        self.error = error
        self.since = since
        self.count = count
    }

    /// The run after one more failed poll: the newest error, the original start, one more in a row.
    public static func next(_ error: CLIError, after previous: CLIFailure?, now: Date) -> CLIFailure {
        CLIFailure(error: error, since: previous?.since ?? now, count: (previous?.count ?? 0) + 1)
    }

    /// A lone timeout is usually the Mac stalling for a moment, so it stays hidden unless the next
    /// poll times out too. Every other failure needs a fix and shows at once.
    public var isShown: Bool {
        if case .timedOut = error { return count >= 2 }
        return true
    }
}

public struct Segment: Equatable, Sendable {
    public var color: GridColor
    public var done: Bool

    public init(color: GridColor, done: Bool) {
        self.color = color
        self.done = done
    }
}

/// What the center of the ring shows, most important first.
public enum Center: Equatable, Sendable {
    case none
    case checkinDue
    case chipWaiting(GridColor)
    case weekHit
}

public enum IconState: Equatable, Sendable {
    case error
    case ring(segments: [Segment], center: Center)
}

private let emptyRing: [Segment] = [
    Segment(color: .yellow, done: false), Segment(color: .yellow, done: false),
    Segment(color: .green, done: false), Segment(color: .green, done: false),
]

public func iconState(status: Status?, failure: CLIFailure?) -> IconState {
    if failure != nil || status?.health.ok == false {
        return .error
    }
    guard let status else {
        return .ring(segments: emptyRing, center: .none)
    }
    let segments = status.units.map { Segment(color: $0.color, done: $0.done) }
    let center: Center
    if status.checkin.due {
        center = .checkinDue
    } else if let chip = status.chips.pending.first {
        center = .chipWaiting(chip.color)
    } else if status.week.hit {
        center = .weekHit
    } else {
        center = .none
    }
    return .ring(segments: segments, center: center)
}

public func iconAccessibilityLabel(_ state: IconState) -> String {
    switch state {
    case .error:
        return "Solve It Grid needs attention"
    case let .ring(segments, center):
        let base = "Solve It Grid: \(segments.filter(\.done).count) of \(segments.count) done"
        switch center {
        case .none: return base
        case .checkinDue: return base + ", check-in due"
        case .chipWaiting: return base + ", chip waiting"
        case .weekHit: return base + ", week hit"
        }
    }
}
