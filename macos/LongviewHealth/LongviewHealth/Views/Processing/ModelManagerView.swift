import SwiftUI

/// Sheet shown when the extraction model is not yet downloaded.
/// Checks model status on appear, offers download, and streams progress.
struct ModelManagerView: View {
    @Binding var isPresented: Bool

    @State private var phase: Phase = .checking
    @State private var lines: [String] = []

    private enum Phase {
        case checking
        case needsDownload
        case downloading
        case done
        case error(String)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Extraction Model")
                        .font(.title3.weight(.semibold))
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                headerAction
            }
            .padding(20)

            Divider()

            // Content
            switch phase {
            case .checking:
                Spacer()
                ProgressView("Checking model status...")
                Spacer()

            case .needsDownload:
                VStack(spacing: 16) {
                    Spacer()
                    Image(systemName: "arrow.down.circle")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary)
                    Text("Longview Health uses a local AI model to extract medical results from your documents.")
                        .multilineTextAlignment(.center)
                    Text("The model is approximately 2 GB and will be downloaded once.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Download Model") {
                        phase = .downloading
                        Task { await startDownload() }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    Spacer()
                }
                .padding(32)

            case .downloading:
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                                Text(line)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundStyle(line.hasPrefix("[error]") ? .red : .primary)
                                    .textSelection(.enabled)
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

            case .done:
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(.green)
                    Text("Model ready!")
                        .font(.title3.weight(.medium))
                }
                Spacer()

            case .error(let message):
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 48))
                        .foregroundStyle(.orange)
                    Text("Download failed")
                        .font(.title3.weight(.medium))
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Button("Retry") {
                        phase = .downloading
                        lines = []
                        Task { await startDownload() }
                    }
                }
                Spacer()
            }
        }
        .frame(minWidth: 480, idealWidth: 520, minHeight: 320, idealHeight: 380)
        .task { await checkStatus() }
    }

    private var subtitle: String {
        switch phase {
        case .checking: return "Checking..."
        case .needsDownload: return "Download required"
        case .downloading: return "Downloading..."
        case .done: return "Ready"
        case .error: return "Error"
        }
    }

    @ViewBuilder
    private var headerAction: some View {
        switch phase {
        case .downloading:
            ProgressView()
                .controlSize(.small)
        case .done:
            Button("Done") { isPresented = false }
                .keyboardShortcut(.cancelAction)
        case .needsDownload:
            Button("Skip") { isPresented = false }
        default:
            EmptyView()
        }
    }

    private func checkStatus() async {
        let (isDownloaded, _) = await CLIRunner.shared.modelStatus()
        if isDownloaded {
            // Model already present -- dismiss immediately
            isPresented = false
        } else {
            phase = .needsDownload
        }
    }

    private func startDownload() async {
        for await line in CLIRunner.shared.modelDownload() {
            lines.append(line)
        }
        // Verify it actually downloaded
        let (isDownloaded, _) = await CLIRunner.shared.modelStatus()
        if isDownloaded {
            phase = .done
        } else {
            let lastError = lines.last { $0.hasPrefix("[error]") } ?? "Unknown error"
            phase = .error(lastError)
        }
    }
}
