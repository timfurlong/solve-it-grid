import Foundation

/// Raw bytes of a JSON fixture in Tests/SolveItGridCoreTests/Fixtures.
func fixture(_ name: String) throws -> Data {
    guard let url = Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures") else {
        throw CocoaError(.fileNoSuchFile)
    }
    return try Data(contentsOf: url)
}
