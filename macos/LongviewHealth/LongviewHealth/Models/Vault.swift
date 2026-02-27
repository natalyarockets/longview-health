import Foundation

/// A vault discovered on the filesystem.
/// Not a database record -- built by scanning ~/.longview/vaults/.
struct DiscoveredVault: Identifiable, Hashable, Sendable {
    let name: String
    let dbPath: URL
    let documentsPath: URL?

    var id: String { name }

    var displayName: String {
        name.replacingOccurrences(of: "-", with: " ").capitalized
    }
}
