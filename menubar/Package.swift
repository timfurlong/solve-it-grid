// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SolveItGrid",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "SolveItGrid", targets: ["SolveItGrid"]),
    ],
    targets: [
        // Every decision lives here, Foundation only, so it can be unit tested.
        .target(name: "SolveItGridCore"),
        // Thin AppKit shell: status item, popover, notifications.
        .executableTarget(name: "SolveItGrid", dependencies: ["SolveItGridCore"]),
        .testTarget(
            name: "SolveItGridCoreTests",
            dependencies: ["SolveItGridCore"],
            resources: [.copy("Fixtures")]
        ),
    ],
    swiftLanguageModes: [.v5]
)
