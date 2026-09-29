import Foundation

/// The five Solve It Grid colors, as named in `solve-it-grid status --json`.
public enum GridColor: String, Decodable, Equatable, Sendable {
    case red, yellow, green, blue, unscored
}

/// Mirror of `solve-it-grid status --json`. Unknown keys are ignored so a newer CLI still decodes.
public struct Status: Decodable, Equatable, Sendable {
    public var generatedAt: String
    public var week: Week
    public var units: [Unit]
    public var redDone: Int
    public var chips: Chips
    public var streak: Streak
    public var checkin: Checkin
    public var lastWeek: LastWeek?
    public var history: [HistoryWeek]
    public var health: Health

    public static func decode(_ data: Data) throws -> Status {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Status.self, from: data)
    }
}

public struct Week: Decodable, Equatable, Sendable {
    public var start: String
    public var end: String
    public var hit: Bool
}

public struct Unit: Decodable, Equatable, Sendable {
    public var id: String
    public var color: GridColor
    public var label: String
    public var done: Bool
}

public struct Chips: Decodable, Equatable, Sendable {
    public var pending: [Chip]
    public var totalEarned: Int
}

public struct Chip: Decodable, Equatable, Sendable {
    public var id: Int
    public var weekStart: String
    public var unit: String
    public var color: GridColor
    public var awardedAt: String
}

public struct Streak: Decodable, Equatable, Sendable {
    public var current: Int
    public var best: Int

    public init(current: Int, best: Int) {
        self.current = current
        self.best = best
    }
}

public struct Checkin: Decodable, Equatable, Sendable {
    public var workday: Bool
    public var due: Bool
    public var done: Bool
    public var steps: [Step]
}

public struct Step: Decodable, Equatable, Sendable {
    public var id: String
    public var label: String
    public var done: Bool
    public var manual: Bool
    public var links: [Link]
}

public struct Link: Decodable, Equatable, Sendable {
    public var label: String
    public var url: String
}

public struct LastWeek: Decodable, Equatable, Sendable {
    public var start: String
    public var hit: Bool

    public init(start: String, hit: Bool) {
        self.start = start
        self.hit = hit
    }
}

public struct HistoryWeek: Decodable, Equatable, Sendable {
    public var start: String
    public var unitsDone: Int
    public var hit: Bool
    public var chips: Int
}

public struct Health: Decodable, Equatable, Sendable {
    public var ok: Bool
    public var errors: [HealthError]
}

public struct HealthError: Decodable, Equatable, Sendable {
    public var source: String
    public var message: String
    public var since: String?
}
