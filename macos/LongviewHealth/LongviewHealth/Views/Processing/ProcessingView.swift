import SwiftUI

/// Modal sheet shown during CLI operations (rescan, export).
/// Streams stdout from the CLI process in real time.
struct ProcessingView: View {
    let vaultName: String
    @Binding var isPresented: Bool

    @State private var lines: [String] = []
    @State private var isRunning = true
    @State private var currentFile: String?
    @State private var filesProcessed = 0
    @State private var resultsStored = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(isRunning ? "Scanning \(vaultName)..." : "Scan Complete")
                        .font(.title3.weight(.semibold))
                    if isRunning, let currentFile {
                        Text(currentFile)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }
                Spacer()
                if isRunning {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Button("Done") { isPresented = false }
                        .keyboardShortcut(.cancelAction)
                }
            }
            .padding(20)

            // Live stats bar
            if filesProcessed > 0 || resultsStored > 0 {
                HStack(spacing: 16) {
                    Label("\(filesProcessed) files", systemImage: "doc")
                    Label("\(resultsStored) results", systemImage: "list.bullet.rectangle")
                }
                .font(.caption.weight(.medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 20)
                .padding(.bottom, 12)
            }

            Divider()

            // Log output
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                            logLine(line)
                                .id(index)
                        }
                    }
                    .padding(16)
                }
                .onChange(of: lines.count) { _, _ in
                    if let last = lines.indices.last {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(.background.secondary)
        }
        .frame(minWidth: 540, idealWidth: 640, minHeight: 380, idealHeight: 440)
        .task { await runScan() }
    }

    @ViewBuilder
    private func logLine(_ line: String) -> some View {
        let style = lineStyle(for: line)
        Text(line)
            .font(.system(.caption, design: .monospaced))
            .foregroundStyle(style.color)
            .fontWeight(style.bold ? .semibold : .regular)
            .textSelection(.enabled)
    }

    private struct LineStyle {
        var color: Color = .primary
        var bold: Bool = false
    }

    private func lineStyle(for line: String) -> LineStyle {
        if line.hasPrefix("[error]") || line.contains("error:") {
            return LineStyle(color: .red)
        }
        if line.contains(": done (") {
            return LineStyle(color: .green)
        }
        if line.contains(": processing") {
            return LineStyle(color: .blue)
        }
        if line.contains(": skipped") {
            return LineStyle(color: .secondary)
        }
        if line.hasPrefix("Files found:") || line.hasPrefix("Results stored:")
            || line.hasPrefix("Parsed:") || line.hasPrefix("PDF report:") {
            return LineStyle(bold: true)
        }
        return LineStyle()
    }

    private func runScan() async {
        for await line in CLIRunner.shared.runRescan(vaultName: vaultName) {
            lines.append(line)
            parseLiveStats(line)
        }
        isRunning = false
    }

    /// Parse CLI output to update live counters and current file name.
    private func parseLiveStats(_ line: String) {
        // Lines like "  filename.pdf: processing"
        if line.contains(": processing") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            currentFile = String(trimmed.prefix(while: { $0 != ":" }))
        }

        // Lines like "  filename.pdf: done (5 results)"
        if line.contains(": done (") {
            filesProcessed += 1
            // Extract result count from "done (N results)"
            if let range = line.range(of: "done ("),
               let endRange = line.range(of: " results)", range: range.upperBound..<line.endIndex) {
                let countStr = line[range.upperBound..<endRange.lowerBound]
                if let count = Int(countStr) {
                    resultsStored += count
                }
            } else if line.contains("done (0 results)") {
                // handled above, but just in case
            }
            currentFile = nil
        }

        // "  filename.pdf: skipped (unchanged)"
        if line.contains(": skipped") {
            currentFile = nil
        }
    }
}
