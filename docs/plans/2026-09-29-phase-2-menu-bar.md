# Phase 2: Menu Bar App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the macOS menu bar app that shows the week's ring, runs the daily check-in popover, and posts check-in, chip and error notifications, all driven by `solve-it-grid status --json`.

**Architecture:** A Swift package in `menubar/` with two targets:
- **`SolveItGridCore`** (Foundation only, fully unit tested) decodes the status JSON, runs the `solve-it-grid` CLI, and holds every decision: icon state, chip board, copy, error reports and notification planning.
- **`SolveItGrid`** (the executable) is a thin AppKit shell:
  - an `NSStatusItem` whose image is drawn from `IconState`
  - an `NSPopover` hosting SwiftUI views
  - an `NSWindow` for history
  - `UNUserNotificationCenter` for notifications

The app never touches Things or the state database. It reads through `solve-it-grid status --json` and writes through `solve-it-grid chip ack`, `checkin done` and `checkin tick`.

**Tech Stack:** Swift 6.x toolchain (Swift 5 language mode), SwiftPM, AppKit, SwiftUI, UserNotifications, ServiceManagement, Swift Testing.

**Spec:** `docs/specs/2026-09-28-solve-it-grid-design.md` (phase 2 of 2: "Menu bar app", "Error state", and the `status --json` contract). Local visual reference, gitignored and not a contract: `docs/explorations/menu-bar-options.html`, option D with icon 5.

## Global Constraints

- **Package:** `menubar/Package.swift`, swift-tools-version 6.0, `platforms: [.macOS(.v14)]`, `swiftLanguageModes: [.v5]`. Targets are `SolveItGridCore` (library), `SolveItGrid` (executable) and `SolveItGridCoreTests`. No third-party dependencies.
- **`SolveItGridCore` imports Foundation only** (no AppKit or SwiftUI), so every decision is unit tested with `cd menubar && swift test`.
- **Bundle:**
  - id `com.github.timfurlong.solve-it-grid`
  - name `Solve It Grid`, executable `SolveItGrid`
  - `LSUIElement` true (no Dock icon), `LSMinimumSystemVersion` 14.0
- **CLI path:** `~/.local/bin/solve-it-grid`, overridable with the UserDefaults key `cliPath`.
- **Timings:**
  - poll every 60 s, when the popover opens, and on wake
  - `status` timeout 10 s
  - snooze 1 hour
  - error re-notification every 2 hours
  - chip pulse 0.8 s per phase
- **Colors:** `NSColor.systemRed`, `.systemYellow`, `.systemGreen`, `.systemBlue`. The check-in-due dot is `.systemOrange`. Open ring segments use `labelColor` at 30% alpha, drawn inside an `NSImage` drawing handler so they follow light and dark mode.
- **Signing:** `menubar/scripts/build-app.sh` uses the first "Apple Development" identity from `security find-identity -v -p codesigning`, and falls back to ad-hoc (`-`). No identity, team id or other personal data is committed.
- **Exact copy** (from the spec's popover):
  - "This week's chips"
  - chip states "In the jar", "Move it now", "Not yet"
  - "I moved the yellow chip" / "I moved 2 chips"
  - "3 reds finished, not scored" / "1 red finished, not scored"
  - "Today's check-in", "4 left"
  - "Snooze 1 hour", "Done for today"
  - "3-week streak", "14 chips earned", "History"
  - "Last week: hit" / "Last week: missed"
- **Notification copy:**

  | Notification | Title | Body |
  |---|---|---|
  | Check-in | "Time for your check-in" | "4 steps left" (or "1 step left") |
  | Chip | "Chip earned" | "Home yellow done. Move a yellow chip." |
  | Error | "Solve It Grid needs attention" | the error report's detail |

- **Human gates.** Ask the user in chat and wait for a yes before:
  - installing the app into `~/Applications`
  - launching it for the first time (it asks for notification permission)
  - registering the login item
  - taking screenshots of the desktop

  Those steps are marked **GATE**.
- Prose, docs and commit messages use no em dashes. Commit messages carry no attribution lines.
- Build and test from `menubar/`: `swift build` and `swift test`.

## Review Focus

1. **The Mac wakes after hours asleep past 9:00, or with an error ongoing.** The user gets one check-in notification and at most one error notification, not a burst. Test in Task 5.
2. **The CLI is missing or moved** (for example after a uv reinstall). The app shows the error triangle and a banner with the install command, and doesn't crash. Tests in Task 4 and Task 5.
3. **Status JSON from a first week or a newer CLI:** `last_week` is null, `history` is empty, a step has no links, or there are unknown extra keys. It still decodes. Test in Task 1.
4. **Monday with last week's chip still pending plus a new chip this week.** The old chip shows as its own row, and the acknowledge button acks both. Test in Task 3.
5. **`solve-it-grid status` hangs** (for example the Things database is locked). It times out at 10 s, the app shows the error state, and the UI stays responsive. Test in Task 4.

---

### Task 1: Package and status decoding

**Files:**
- Create: `menubar/Package.swift`, `menubar/Sources/SolveItGridCore/Status.swift`, `menubar/Sources/SolveItGrid/main.swift` (placeholder `print("SolveItGrid")`, replaced in Task 6)
- Test: `menubar/Tests/SolveItGridCoreTests/StatusTests.swift`, `menubar/Tests/SolveItGridCoreTests/Fixtures/status-thursday.json`, `menubar/Tests/SolveItGridCoreTests/Fixtures/status-first-week.json`

**Interfaces:**
- Produces (all `public`, `Decodable`, `Equatable`; decoded with `keyDecodingStrategy = .convertFromSnakeCase`; unknown keys ignored):
  - `enum GridColor: String { case red, yellow, green, blue, unscored }`
  - `struct Status { generatedAt: String; week: Week; units: [Unit]; redDone: Int; chips: Chips; streak: Streak; checkin: Checkin; lastWeek: LastWeek?; history: [HistoryWeek]; health: Health }`
  - `Week { start: String; end: String; hit: Bool }`
  - `Unit { id: String; color: GridColor; label: String; done: Bool }`
  - `Chips { pending: [Chip]; totalEarned: Int }`
  - `Chip { id: Int; weekStart: String; unit: String; color: GridColor; awardedAt: String }`
  - `Streak { current: Int; best: Int }`
  - `Checkin { workday: Bool; due: Bool; done: Bool; steps: [Step] }`
  - `Step { id: String; label: String; done: Bool; manual: Bool; links: [Link] }`
  - `Link { label: String; url: String }`
  - `LastWeek { start: String; hit: Bool }`
  - `HistoryWeek { start: String; unitsDone: Int; hit: Bool; chips: Int }`
  - `Health { ok: Bool; errors: [HealthError] }`, `HealthError { source: String; message: String; since: String? }`
  - `static func Status.decode(_ data: Data) throws -> Status`

- [ ] **Step 1: Write `Package.swift`** per Global Constraints. The test target has `resources: [.copy("Fixtures")]`.
- [ ] **Step 2: Write the fixtures.**
  - `status-thursday.json` is the spec's example (`solve-it-grid status --json` section), extended so it has:
    - all four units: yellow-work done, yellow-home done, green-1 done, green-2 not
    - one pending chip for `yellow-home` with `week_start` `2026-09-28`
    - `red_done` 3
    - `streak` {3, 5} and `total_earned` 14
    - the check-in steps from the spec popover (inbox, red and yellow done; green, today-reviewed and colors-reviewed open; areas open), with manual true only for the two review steps
    - `last_week` {"2026-09-21", true}
    - two history rows
    - an extra top-level key `"future_field": 1`
  - `status-first-week.json` has `last_week: null`, `history: []`, `chips.pending: []`, and one step whose `links` is `[]`.
- [ ] **Step 3: Write failing tests**

  ```swift
  @Test func decodesThursdayFixture() throws {
      let s = try Status.decode(fixture("status-thursday"))
      #expect(s.units.map(\.id) == ["yellow-work", "yellow-home", "green-1", "green-2"])
      #expect(s.chips.pending.first?.weekStart == "2026-09-28")
      #expect(s.redDone == 3 && s.streak == Streak(current: 3, best: 5))
      #expect(s.checkin.steps.filter(\.manual).map(\.id) == ["today-reviewed", "colors-reviewed"])
  }
  @Test func decodesFirstWeekWithNullsAndEmptyLists() throws {
      let s = try Status.decode(fixture("status-first-week"))
      #expect(s.lastWeek == nil && s.history.isEmpty && s.chips.pending.isEmpty)
  }
  @Test func unknownColorFailsLoudly() { /* "purple" in a unit -> Status.decode throws */ }
  ```

- [ ] **Step 4:** Run `cd menubar && swift test`. Expected: FAIL (types missing).
- [ ] **Step 5: Implement `Status.swift`.**
- [ ] **Step 6:** Run `swift test`. Expected: PASS. Also run `swift build`, which should build both targets.
- [ ] **Step 7: Commit**: `git commit -m "Add menu bar package and status decoding"`

### Task 2: Icon state and copy

**Files:**
- Create: `menubar/Sources/SolveItGridCore/IconState.swift`, `menubar/Sources/SolveItGridCore/Copy.swift`
- Test: `menubar/Tests/SolveItGridCoreTests/IconStateTests.swift`, `menubar/Tests/SolveItGridCoreTests/CopyTests.swift`

**Interfaces:**
- Consumes: `Status`, `GridColor` (Task 1). `CLIFailure` is declared here and is used by Tasks 4 and 5.
- Produces:
  - `enum CLIError: Error, Equatable { case notFound(path: String), timedOut(seconds: Double), failed(exitCode: Int32, stderr: String), decoding(String) }`
  - `struct CLIFailure: Equatable { error: CLIError; since: Date }`
  - `struct Segment: Equatable { color: GridColor; done: Bool }`
  - `enum Center: Equatable { case none, checkinDue, chipWaiting(GridColor), weekHit }`
  - `enum IconState: Equatable { case error; case ring(segments: [Segment], center: Center) }`
  - `func iconState(status: Status?, failure: CLIFailure?) -> IconState`
  - `func iconAccessibilityLabel(_ state: IconState) -> String`
  - Copy functions:
    - `Copy.redLine(_ n: Int) -> String`
    - `Copy.leftLine(_ n: Int) -> String` ("4 left")
    - `Copy.streakLine(_ n: Int) -> String` ("3-week streak")
    - `Copy.chipsEarnedLine(_ n: Int) -> String` ("14 chips earned", "1 chip earned")
    - `Copy.stepsLeftBody(_ n: Int) -> String` ("4 steps left", "1 step left")
    - `Copy.lastWeekLine(_ lastWeek: LastWeek?, isMonday: Bool) -> String?`
- Rules:
  - **The state is `.error`** when `failure != nil` or `status?.health.ok == false`.
  - **Segments** follow `status.units` in order (drawn clockwise from 12 o'clock). A nil status gives four open segments `[yellow, yellow, green, green]`.
  - **The center** follows the spec's priority:
    1. `checkin.due` → `.checkinDue`
    2. any pending chip → `.chipWaiting(first pending chip's color)`
    3. `week.hit` → `.weekHit`
    4. otherwise `.none`
  - **Accessibility labels:**
    - `"Solve It Grid needs attention"` in the error state
    - otherwise `"Solve It Grid: 3 of 4 done"`, plus `", check-in due"`, `", chip waiting"` or `", week hit"` for the center

- [ ] **Step 1: Write failing tests**
  - `errorWhenFailure`
  - `errorWhenHealthNotOk`
  - `segmentsFollowUnits` (Thursday fixture gives `[y done, y done, g done, g open]`)
  - `checkinDueBeatsChipWaiting`
  - `chipWaitingBeatsWeekHit`
  - `weekHitCenter`
  - `nilStatusIsFourOpenSegments`
  - `accessibilityLabelThursday == "Solve It Grid: 3 of 4 done, check-in due"`
  - one test per copy function covering the singular and plural forms
  - `lastWeekLineOnlyOnMonday` (nil when `isMonday` is false or `lastWeek` is nil; `"Last week: missed"` when hit is false)
- [ ] **Step 2:** Run `swift test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Run `swift test`. Expected: PASS. Commit: `git commit -m "Add icon state and popover copy"`

### Task 3: Chip board

**Files:**
- Create: `menubar/Sources/SolveItGridCore/ChipBoard.swift`
- Test: `menubar/Tests/SolveItGridCoreTests/ChipBoardTests.swift`

**Interfaces:**
- Consumes: `Status`, `Chip`, `Unit`, `GridColor`.
- Produces:
  - `enum SlotState: Equatable { case earned, pending(chipID: Int), open }` with `var caption: String`: "In the jar", "Move it now", "Not yet"
  - `struct ChipSlot: Equatable { unitID: String; label: String; color: GridColor; state: SlotState }`
  - `struct LeftoverChip: Equatable { chip: Chip; label: String }`
  - `struct ChipBoard: Equatable { slots: [ChipSlot]; leftovers: [LeftoverChip]; pendingIDs: [Int]; ackLabel: String? }`
  - `func chipBoard(for status: Status) -> ChipBoard`
- Rules:
  - One slot per unit, in unit order.
  - A slot is `.pending` when a pending chip has the same `unit` and `weekStart == status.week.start`. Otherwise it's `.earned` when the unit is done, and `.open` otherwise.
  - Pending chips from another week become `leftovers`. The leftover label is the current unit label with the same id, or the unit id if there's none.
  - `pendingIDs` lists every pending chip id, including leftovers.
  - `ackLabel`:
    - nil when nothing is pending
    - `"I moved the <color> chip"` for exactly one
    - `"I moved <n> chips"` for more than one

- [ ] **Step 1: Write failing tests**

  ```swift
  @Test func thursdayBoard() throws {
      let b = chipBoard(for: try Status.decode(fixture("status-thursday")))
      #expect(b.slots.map(\.state) == [.earned, .pending(chipID: 57), .earned, .open])
      #expect(b.slots.map(\.state.caption) == ["In the jar", "Move it now", "In the jar", "Not yet"])
      #expect(b.ackLabel == "I moved the yellow chip" && b.leftovers.isEmpty)
  }
  @Test func mondayLeftoverFromLastWeekPlusNewChip() { /* week.start 2026-10-05; pending [57 yellow-home 2026-09-28, 61 green-1 2026-10-05]
      -> green-1 slot .pending(61); one leftover (57, "Home yellow"); pendingIDs [57, 61]; ackLabel "I moved 2 chips" */ }
  @Test func noPendingNoAckLabel() { ... }
  ```

- [ ] **Step 2:** Run `swift test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Run `swift test`. Expected: PASS. Commit: `git commit -m "Add chip board model"`

### Task 4: CLI client

**Files:**
- Create: `menubar/Sources/SolveItGridCore/CLIClient.swift`
- Test: `menubar/Tests/SolveItGridCoreTests/CLIClientTests.swift`

**Interfaces:**
- Consumes: `Status.decode`, `CLIError` (Task 2).
- Produces:
  - `struct CommandResult: Equatable { exitCode: Int32; stdout: Data; stderr: String }`
  - `protocol CommandRunner: Sendable { func run(_ executable: URL, _ arguments: [String], timeout: TimeInterval) async throws -> CommandResult }`
  - `struct ProcessRunner: CommandRunner`
    - Runs `Process` with stdout and stderr pipes, off the main thread.
    - On timeout it terminates the process and throws `CLIError.timedOut(seconds:)`.
  - `struct CLIClient`
    - `init(executable: URL, runner: CommandRunner = ProcessRunner(), timeout: TimeInterval = 10)`
    - `func status() async throws -> Status`
    - `func ackChips(_ ids: [Int]) async throws`
    - `func checkinDone() async throws`
    - `func tick(_ step: String) async throws`
  - `static func CLIClient.defaultExecutable(defaults: UserDefaults = .standard) -> URL`: the `cliPath` value, or `~/.local/bin/solve-it-grid`
- Rules:
  - Arguments:
    - `["status", "--json"]`
    - `["chip", "ack"] + ids.map(String.init)` (`ackChips([])` doesn't run anything)
    - `["checkin", "done"]`
    - `["checkin", "tick", step]`
  - When the executable isn't executable (`FileManager.isExecutableFile`), throw `.notFound(path:)` without running anything.
  - A non-zero exit throws `.failed(exitCode:stderr:)` with the trimmed stderr.
  - Bad JSON throws `.decoding(message)`.

- [ ] **Step 1: Write failing tests**
  - Using a `FakeRunner` that records calls and returns a canned `CommandResult`:
    - `statusArgumentsAndDecode`
    - `ackArgumentsAndEmptyIsNoop`
    - `tickArguments`
    - `nonZeroExitThrowsFailedWithStderr`
    - `badJSONThrowsDecoding`
    - `missingExecutableThrowsNotFound` (path `/nonexistent/solve-it-grid`)
  - Using the real `ProcessRunner`:
    - `processRunnerCapturesOutput`: `/bin/echo hi` gives stdout `"hi\n"`, exit 0
    - `processRunnerTimesOut`: `/bin/sleep 5` with timeout 0.5 throws `.timedOut` within 2 s
- [ ] **Step 2:** Run `swift test`. Expected: FAIL.
- [ ] **Step 3: Implement.** `ProcessRunner` bridges `terminationHandler` into async with a checked continuation, and races a timeout task that calls `terminate()`.
- [ ] **Step 4:** Run `swift test`. Expected: PASS. Commit: `git commit -m "Add CLI client with timeout"`

### Task 5: Error reports and notification planning

**Files:**
- Create: `menubar/Sources/SolveItGridCore/ErrorReport.swift`, `menubar/Sources/SolveItGridCore/NotificationPlanner.swift`
- Test: `menubar/Tests/SolveItGridCoreTests/ErrorReportTests.swift`, `menubar/Tests/SolveItGridCoreTests/NotificationPlannerTests.swift`

**Interfaces:**
- Consumes: `Status`, `CLIFailure`, `CLIError`, `Copy`, `chipBoard` labels (unit label lookup).
- Produces:
  - `struct ErrorReport: Equatable { title: String; detail: String; fix: String?; since: String? }` and `func errorReport(failure: CLIFailure?, status: Status?) -> ErrorReport?`
  - `struct NotificationMemory: Codable, Equatable { var initialized = false; var checkinNotifiedDay: String?; var snoozedUntil: Date?; var seenChipIDs: Set<Int> = []; var errorSince: Date?; var lastErrorNotifiedAt: Date? }`
  - `enum PlannedNotification: Equatable { case checkin(stepsLeft: Int); case chip(id: Int, body: String); case error(ErrorReport) }`
  - `func planNotifications(now: Date, calendar: Calendar, status: Status?, failure: CLIFailure?, memory: NotificationMemory) -> (notifications: [PlannedNotification], memory: NotificationMemory)`
  - `func snoozed(_ memory: NotificationMemory, now: Date) -> NotificationMemory` (sets `snoozedUntil = now + 3600`)
- `errorReport` rules (a failure takes precedence over health errors):

  | Condition | title | detail | fix |
  |---|---|---|---|
  | `.notFound(path)` | "solve-it-grid not found" | the path | "Install it from the repo: uv tool install --editable ./engine" |
  | `.timedOut` | "solve-it-grid status timed out" | "No answer after 10 seconds." | "Check that Things is running." |
  | `.failed(_, stderr)` | "solve-it-grid status failed" | the last non-empty stderr line | nil |
  | `.decoding` | "Unexpected status output" | the message | "Rebuild the app after updating the CLI." |
  | health errors | "Setup needs attention" if any error's source is `setup`, else "Categorizer needs attention" | messages joined with a newline | "Claude Code is not logged in: run `claude` in a terminal." when a message contains "logged in" (case-insensitive), else nil |

  `since` is the first health error's `since`, or nil. The result is nil when there's no failure and health is ok.
- `planNotifications` rules:
  - **Day keys** are `yyyy-MM-dd` in `calendar`'s time zone.
  - **First call** (`initialized == false`): mark all current pending chip ids as seen, notify none of them, and set `initialized`.
  - **Check-in:** only when `failure == nil` and `status.checkin.due`. Post when `snoozedUntil` has passed, or when there's no snooze and `checkinNotifiedDay != today`. After posting, set `checkinNotifiedDay = today` and `snoozedUntil = nil`.
  - **Chips:** each pending id not in `seenChipIDs` gives `.chip(id:body:)` with body "<unit label> done. Move a <color> chip.", and is then added to the seen set.
  - **Error:**
    - It's active when `errorReport(...) != nil`.
    - When it becomes active, set `errorSince = now` and post.
    - While it stays active, post again when `now - lastErrorNotifiedAt >= 2 h`.
    - When it clears, reset both fields.

- [ ] **Step 1: Write failing tests**
  - `ErrorReportTests`: one per table row, plus `loggedInHint` and `nilWhenHealthy`.
  - `NotificationPlannerTests`, with a fixed UTC calendar and dates on 2026-10-01:
    - `checkinPostsOnceWhenDue` (09:01 posts `.checkin(stepsLeft: 4)`; 09:02 posts nothing)
    - `snoozeRepostsAfterAnHour` (snooze at 09:05; 09:30 nothing; 10:05 posts)
    - `notDueNoCheckin`
    - `firstRunSeedsChipsWithoutNotifying`
    - `newChipNotifiedOnce` (body `"Home yellow done. Move a yellow chip."`)
    - `errorNotifiesOnStartAndEveryTwoHours` (t0 posts, +1h nothing, +2h posts, cleared resets)
    - `wakeAfterLongSleepPostsOneOfEach` (memory from yesterday 09:01, error active since 10 h ago with last notification 10 h ago, now 11:00 and due: exactly `[.checkin, .error]`, one each)
- [ ] **Step 2:** Run `swift test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Run `swift test`. Expected: PASS. Commit: `git commit -m "Add error reports and notification planning"`

### Task 6: App shell, bundle and status icon

**Files:**
- Create:
  - `menubar/Sources/SolveItGrid/main.swift` (replaces the placeholder)
  - `menubar/Sources/SolveItGrid/AppDelegate.swift`
  - `menubar/Sources/SolveItGrid/AppModel.swift`
  - `menubar/Sources/SolveItGrid/StatusIconRenderer.swift`
  - `menubar/Bundle/Info.plist`
  - `menubar/scripts/build-app.sh`

**Interfaces:**
- Consumes: `CLIClient`, `iconState`, `iconAccessibilityLabel`, `planNotifications`, `NotificationMemory`.
- Produces:
  - `@MainActor @Observable final class AppModel`
    - Properties: `status: Status?` (last good), `failure: CLIFailure?`, `memory: NotificationMemory` (persisted as JSON in UserDefaults under `notificationMemory`).
    - `func refresh() async`: calls `client.status()`; on success it sets `status` and clears `failure`; on a `CLIError` it sets `failure` (keeping `since` from the first failure in the streak). It then runs `planNotifications` and hands the notifications to `onNotify`.
    - Actions: `func ackAll() async`, `func checkinDone() async`, `func tick(_ step: String) async`, and `func snooze()`. Each action refreshes afterwards.
    - `var onChange: (() -> Void)?`, which the delegate uses to redraw the icon.
    - `var onNotify: (([PlannedNotification]) -> Void)?`
  - `enum StatusIconRenderer { static func image(for state: IconState, pulseOn: Bool) -> NSImage }`
    - An 18x18 pt image with `isTemplate = false`.
    - The ring: radius 6.2, segment line width 2.6 (open 2.0), segments spanning 90° minus a 12° gap each.
    - The center: an orange dot of radius 2.3, a chip-colored dot of radius 2.4 (alpha 0.35 when `pulseOn` is false), or a checkmark.
    - The error state: the SF Symbol `exclamationmark.triangle.fill` with hierarchical color `.systemRed`.
    - Everything is drawn in `NSImage(size:flipped:drawingHandler:)`, so colors follow the current appearance.
- `AppDelegate`:
  - Sets the activation policy to `.accessory`.
  - Creates the `NSStatusItem` (variable length).
  - Polls with a 60 s `Timer` and refreshes on `NSWorkspace.didWakeNotification`.
  - Runs a pulse `Timer` (0.8 s) only while the center is `.chipWaiting` and `NSWorkspace.shared.accessibilityDisplayShouldReduceMotion` is false.
  - Sets `statusItem.button.setAccessibilityLabel` from `iconAccessibilityLabel`.
  - Clicking the button toggles the popover. The popover arrives in Task 7; this task logs the click.
- `build-app.sh [--install]`:
  1. Runs `swift build -c release --product SolveItGrid`.
  2. Assembles `menubar/build/Solve It Grid.app` (`Contents/MacOS/SolveItGrid`, `Contents/Info.plist`).
  3. Signs it with `codesign --force --options runtime --sign "<identity or ->"`.
  4. With `--install`, replaces `~/Applications/Solve It Grid.app` and runs `open` on it.

- [ ] **Step 1:** Write `Info.plist` (keys per Global Constraints, `CFBundleShortVersionString` 0.1.0, `CFBundleVersion` 1) and `build-app.sh` (`set -euo pipefail`, executable bit set).
- [ ] **Step 2:** Implement `main.swift`, `AppDelegate`, `AppModel` and `StatusIconRenderer`.
- [ ] **Step 3:** Run `swift build && swift test`. Expected: both succeed, and all Core tests still pass.
- [ ] **Step 4:** Run `scripts/build-app.sh` (no install). Expected: it prints the signing identity used (or `ad-hoc`), and `codesign --verify --verbose "build/Solve It Grid.app"` reports valid.
- [ ] **Step 5: Commit**: `git commit -m "Add menu bar app shell, icon renderer and build script"`

### Task 7: Popover and history window

**Files:**
- Create:
  - `menubar/Sources/SolveItGrid/Views/PopoverView.swift`
  - `menubar/Sources/SolveItGrid/Views/ChipBoardView.swift`
  - `menubar/Sources/SolveItGrid/Views/PokerChipView.swift`
  - `menubar/Sources/SolveItGrid/Views/CheckinListView.swift`
  - `menubar/Sources/SolveItGrid/Views/ErrorBannerView.swift`
  - `menubar/Sources/SolveItGrid/Views/HistoryView.swift`
- Modify: `menubar/Sources/SolveItGrid/AppDelegate.swift` (the `NSPopover` with `.transient` behavior hosting `PopoverView`; refresh on show; a history `NSWindow` hosting `HistoryView`)

**Interfaces:**
- Consumes: `AppModel`, `chipBoard(for:)`, `errorReport`, `Copy`, `Status`.
- Produces: `AppDelegate.showPopover()`, which Task 8's notification actions call.

- [ ] **Step 1: Build the popover.** The layout follows the spec's popover block, top to bottom:
  1. The `ErrorBannerView`, only when `errorReport` is non-nil: title, detail, fix and "since", in red-tinted styling.
  2. A header with "This week's chips" and the week range (for example "Sep 28 to Oct 4", formatted from `week.start` and `week.end`).
  3. Four `PokerChipView`s from `chipBoard.slots`, each with the unit label and `state.caption`, followed by any leftover rows ("Move it now").
  4. The ack button (`ackLabel`, calls `ackAll`).
  5. `Copy.redLine`.
  6. "Today's check-in" with `Copy.leftLine`, and `Copy.lastWeekLine` when today is Monday.
  7. The steps. Auto steps show a check or a circle. Manual steps show a clickable checkbox that calls `tick`. Each open step's links are buttons that `NSWorkspace.shared.open` the URL.
  8. "Snooze 1 hour" and "Done for today".
  9. A divider, then a footer with `Copy.streakLine`, `Copy.chipsEarnedLine` and "History".
- [ ] **Step 2: Draw `PokerChipView(color:letter:state:size:)`** as in mockup D:
  - A solid disc with eight white edge inserts, a dashed inner ring and the letter (W, H or G).
  - `.open` is a dashed outline.
  - `.pending` is lifted with a shadow and bobs 4 pt over 2.6 s, unless `accessibilityReduceMotion` is on.
- [ ] **Step 3: Build `HistoryView`.** It shows the current and best streak, then one row per `history` week: the start date, units done, hit or missed, and chips.
- [ ] **Step 4:** Run `swift build && swift test`. Expected: success. Commit: `git commit -m "Add popover, poker chips and history window"`

### Task 8: Notifications and login item

**Files:**
- Create: `menubar/Sources/SolveItGrid/NotificationPoster.swift`, `menubar/Sources/SolveItGrid/LoginItem.swift`
- Modify: `menubar/Sources/SolveItGrid/AppDelegate.swift`

**Interfaces:**
- Consumes: `PlannedNotification`, `Copy.stepsLeftBody`, `AppModel.snooze`, `AppDelegate.showPopover`.
- Produces:
  - `final class NotificationPoster: NSObject, UNUserNotificationCenterDelegate`
    - `func requestAuthorization()`
    - `func post(_ n: PlannedNotification)`
    - Category `CHECKIN` has the actions `START` ("Start check-in", foreground) and `SNOOZE` ("Snooze 1 hour"). The chip and error notifications have no category.
    - Check-in content sets `interruptionLevel = .timeSensitive`. The system treats it as active when the app lacks that entitlement.
  - `enum LoginItem { static func registerIfNeeded() }`
    - Calls `SMAppService.mainApp.register()` once.
    - Records the attempt in UserDefaults (`loginItemRegistered`).
    - Logs the resulting `SMAppService.mainApp.status`.
- Delegate handling:
  - `START`, or tapping any of our notifications, calls `showPopover()`.
  - `SNOOZE` calls `model.snooze()`.
  - Notifications show while the app is frontmost (`willPresent` returns `[.banner, .sound]`).

- [ ] **Step 1: Implement**, wiring `AppModel.onNotify` to `poster.post`. `requestAuthorization` and `LoginItem.registerIfNeeded` run in `applicationDidFinishLaunching`.
- [ ] **Step 2:** Run `swift build && swift test`. Expected: success.
- [ ] **Step 3: Commit**: `git commit -m "Add notifications with snooze and the login item"`

### Task 9: Live install and verification

**Files:** none (the outcome is recorded in this plan).

- [ ] **Step 1: GATE.** Ask: "OK to build and install Solve It Grid.app to ~/Applications and launch it? It will ask for notification permission and add itself as a login item." On yes, run `menubar/scripts/build-app.sh --install`.
- [ ] **Step 2:** Ask the user to click Allow on the notification prompt and to set the app's notification style to Alerts (System Settings > Notifications > Solve It Grid). Confirm with them that `SMAppService` shows the login item (System Settings > General > Login Items).
- [ ] **Step 3: GATE.** Ask before taking screenshots. Then verify:
  - the ring matches `solve-it-grid status`
  - the popover shows the chips, the check-in steps and the footer
  - ticking a manual step persists (`solve-it-grid status` shows it done)
  - "History" opens the window
  - light and dark mode both render correctly
- [ ] **Step 4:** Verify the error state without touching real data. Set the `cliPath` default to a nonexistent path (`defaults write com.github.timfurlong.solve-it-grid cliPath /nonexistent`) and relaunch. Expected: the triangle, a banner reading "solve-it-grid not found", and one error notification. Then `defaults delete com.github.timfurlong.solve-it-grid cliPath` and relaunch, and the ring returns.
- [ ] **Step 5:** Record the outcome here, including whether the time-sensitive level took effect and which signing identity was used (by type only, never the name).

### Task 10: README and spec sync

**Files:**
- Modify: `README.md`, `docs/specs/2026-09-28-solve-it-grid-design.md`

- [ ] **Step 1: README.** Add a "Menu bar app" section:
  - build and install (`menubar/scripts/build-app.sh --install`)
  - the notification permission and the Alerts style
  - the login item
  - what the ring and its center mean
  - where to set `cliPath`
- [ ] **Step 2: Spec.** Diff the "Menu bar app" and "Repository" sections against what was built, and correct anything that's now wrong: the notification copy, the build script, and any Task 9 findings.
- [ ] **Step 3: Public-readiness check.** Run `git grep -nIE "Apple Development: |\([A-Z0-9]{10}\)" -- menubar README.md`, which should return nothing. That covers signing identity names and team ids.
- [ ] **Step 4: Commit**: `git commit -m "Document the menu bar app; sync spec"`

This is the last phase in the spec, so there are no later phase plans to review.
