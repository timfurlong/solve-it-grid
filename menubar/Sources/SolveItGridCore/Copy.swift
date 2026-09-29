import Foundation

/// User-facing strings, kept in one place so the popover and notifications agree.
public enum Copy {
    public static func redLine(_ n: Int) -> String {
        n == 1 ? "1 red finished, not scored" : "\(n) reds finished, not scored"
    }

    public static func leftLine(_ n: Int) -> String {
        "\(n) left"
    }

    public static func streakLine(_ n: Int) -> String {
        "\(n)-week streak"
    }

    public static func chipsEarnedLine(_ n: Int) -> String {
        n == 1 ? "1 chip earned" : "\(n) chips earned"
    }

    public static func stepsLeftBody(_ n: Int) -> String {
        n == 1 ? "1 step left" : "\(n) steps left"
    }

    /// Shown under the check-in header on Mondays only.
    public static func lastWeekLine(_ lastWeek: LastWeek?, isMonday: Bool) -> String? {
        guard isMonday, let lastWeek else { return nil }
        return lastWeek.hit ? "Last week: hit" : "Last week: missed"
    }

    /// "Sep 28 to Oct 4" from the status week's ISO dates.
    public static func weekRange(start: String, end: String) -> String {
        "\(shortDate(start)) to \(shortDate(end))"
    }

    /// "Sep 21" from "2026-09-21"; the input is returned unchanged if it isn't a date.
    public static func shortDate(_ isoDay: String) -> String {
        let parse = DateFormatter()
        parse.locale = Locale(identifier: "en_US_POSIX")
        parse.timeZone = TimeZone(identifier: "UTC")
        parse.dateFormat = "yyyy-MM-dd"
        guard let date = parse.date(from: isoDay) else { return isoDay }
        let format = DateFormatter()
        format.locale = Locale(identifier: "en_US_POSIX")
        format.timeZone = TimeZone(identifier: "UTC")
        format.dateFormat = "MMM d"
        return format.string(from: date)
    }

    /// "Since Oct 1, 9:00 AM" from an ISO timestamp (with or without fractional seconds).
    public static func sinceLine(_ iso: String, timeZone: TimeZone = .current) -> String {
        let plain = ISO8601DateFormatter()
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = plain.date(from: iso) ?? fractional.date(from: iso) else { return "Since \(iso)" }
        let format = DateFormatter()
        format.locale = Locale(identifier: "en_US_POSIX")
        format.timeZone = timeZone
        format.dateFormat = "MMM d, h:mm a"
        return "Since \(format.string(from: date))"
    }

    /// Shown under a capped list of links.
    public static func moreLine(_ n: Int) -> String {
        "and \(n) more"
    }
}

/// Caps a step's per-item links so a long backlog can't push the popover's buttons off screen.
public func visibleLinks(_ links: [Link], limit: Int = 5) -> (shown: [Link], hiddenCount: Int) {
    (Array(links.prefix(limit)), max(0, links.count - limit))
}
