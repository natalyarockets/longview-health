import Foundation

/// Shells out to the `longview` CLI for mutations (rescan, export, review actions).
/// The app reads SQLite directly, but all writes go through the CLI to maintain
/// the single-writer contract.
///
/// Resolution order for the executable:
/// 1. Bundled engine (production) -- Resources/longview-engine/longview
/// 2. User override -- ~/.longview/cli_path
/// 3. System PATH -- ~/.local/bin, /opt/homebrew/bin, /usr/local/bin
final class CLIRunner: Sendable {
    static let shared = CLIRunner()

    /// Locate the longview executable.
    private func findExecutable() -> String? {
        // 1. Bundled engine (production -- inside the .app bundle)
        if let bundled = Bundle.main.resourceURL?
            .appendingPathComponent("longview-engine/longview") {
            if FileManager.default.isExecutableFile(atPath: bundled.path) {
                return bundled.path
            }
        }

        // 2. User override (~/.longview/cli_path)
        let overridePath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".longview/cli_path")
        if let override = try? String(contentsOf: overridePath, encoding: .utf8) {
            let trimmed = override.trimmingCharacters(in: .whitespacesAndNewlines)
            if FileManager.default.isExecutableFile(atPath: trimmed) {
                return trimmed
            }
        }

        // 3. System PATH fallbacks
        let candidates = [
            FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".local/bin/longview").path,
            "/opt/homebrew/bin/longview",
            "/usr/local/bin/longview",
        ]

        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    /// Run a CLI command and stream stdout lines.
    func run(arguments: [String]) -> AsyncStream<String> {
        AsyncStream { continuation in
            let executable = self.findExecutable()

            Task.detached {
                guard let executable else {
                    continuation.yield("[error] Could not find 'longview' CLI executable.")
                    continuation.yield("Check ~/.longview/cli_path or install longview.")
                    continuation.finish()
                    return
                }

                let process = Process()
                process.executableURL = URL(fileURLWithPath: executable)
                process.arguments = arguments

                // Inherit PATH so the CLI can find its dependencies
                var env = ProcessInfo.processInfo.environment
                let home = FileManager.default.homeDirectoryForCurrentUser.path
                let extraPaths = [
                    "\(home)/.local/bin",
                    "\(home)/.cargo/bin",
                    "/opt/homebrew/bin",
                    "/usr/local/bin",
                ]
                let currentPath = env["PATH"] ?? "/usr/bin:/bin"
                env["PATH"] = (extraPaths + [currentPath]).joined(separator: ":")
                process.environment = env

                let pipe = Pipe()
                process.standardOutput = pipe
                process.standardError = pipe

                do {
                    try process.run()
                } catch {
                    continuation.yield("[error] Failed to launch CLI: \(error.localizedDescription)")
                    continuation.finish()
                    return
                }

                let handle = pipe.fileHandleForReading
                let data = handle.readDataToEndOfFile()
                if let output = String(data: data, encoding: .utf8) {
                    for line in output.components(separatedBy: .newlines) where !line.isEmpty {
                        continuation.yield(line)
                    }
                }

                process.waitUntilExit()
                continuation.finish()
            }
        }
    }

    /// Convenience: run rescan on a vault.
    func runRescan(vaultName: String) -> AsyncStream<String> {
        run(arguments: ["rescan", vaultName])
    }

    /// Convenience: run export on a vault.
    func runExport(vaultName: String) async -> [String] {
        var lines: [String] = []
        for await line in run(arguments: ["export", vaultName]) {
            lines.append(line)
        }
        return lines
    }

    /// Convenience: accept a review item.
    func reviewAccept(vaultName: String, reviewId: String) async -> [String] {
        var lines: [String] = []
        for await line in run(arguments: ["review", "accept", vaultName, reviewId]) {
            lines.append(line)
        }
        return lines
    }

    /// Convenience: create a new vault.
    func createVault(name: String, documentsPath: String?) async -> [String] {
        var args = ["vault", "create", name]
        if let documentsPath {
            args += ["--path", documentsPath]
        }
        var lines: [String] = []
        for await line in run(arguments: args) {
            lines.append(line)
        }
        return lines
    }

    /// Convenience: reject a review item.
    func reviewReject(vaultName: String, reviewId: String) async -> [String] {
        var lines: [String] = []
        for await line in run(arguments: ["review", "reject", vaultName, reviewId]) {
            lines.append(line)
        }
        return lines
    }

    /// Check whether the extraction model is downloaded.
    func modelStatus() async -> (isDownloaded: Bool, output: [String]) {
        var lines: [String] = []
        for await line in run(arguments: ["model", "status"]) {
            lines.append(line)
        }
        let downloaded = lines.contains { $0.contains("downloaded") && !$0.contains("not downloaded") }
        return (downloaded, lines)
    }

    /// Download the extraction model (streams progress).
    func modelDownload() -> AsyncStream<String> {
        run(arguments: ["model", "download"])
    }
}
