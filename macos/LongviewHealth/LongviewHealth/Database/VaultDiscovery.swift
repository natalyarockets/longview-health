import Foundation

/// Discovers vaults by scanning ~/.longview/vaults/ on the filesystem.
/// Mirrors the logic in core/paths.py.
@Observable
final class VaultDiscovery: Sendable {

    /// Scan the filesystem for existing vaults.
    /// A valid vault is a directory containing vault.db.
    static func discoverVaults() -> [DiscoveredVault] {
        let vaultsRoot = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".longview/vaults")

        guard let entries = try? FileManager.default.contentsOfDirectory(
            at: vaultsRoot,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else {
            return []
        }

        return entries.compactMap { dir in
            let dbPath = dir.appendingPathComponent("vault.db")
            guard FileManager.default.fileExists(atPath: dbPath.path) else {
                return nil
            }

            // Check for external source_path (mirrors core/paths.py:39-41)
            let sourcePathFile = dir.appendingPathComponent("source_path")
            let documentsPath: URL?
            if let raw = try? String(contentsOf: sourcePathFile, encoding: .utf8) {
                let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
                documentsPath = URL(fileURLWithPath: trimmed)
            } else {
                let defaultDocs = dir.appendingPathComponent("documents")
                if FileManager.default.fileExists(atPath: defaultDocs.path) {
                    documentsPath = defaultDocs
                } else {
                    documentsPath = nil
                }
            }

            return DiscoveredVault(
                name: dir.lastPathComponent,
                dbPath: dbPath,
                documentsPath: documentsPath
            )
        }
        .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }
}
