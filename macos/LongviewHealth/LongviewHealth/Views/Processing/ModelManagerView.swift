import SwiftUI

/// Sheet shown when the extraction model is not yet downloaded.
/// Checks model status on appear, offers download or Ollama configuration.
struct ModelManagerView: View {
    @Binding var isPresented: Bool

    @State private var phase: Phase = .checking
    @State private var lines: [String] = []
    @State private var ollamaChecking = false
    @State private var ollamaAvailable = false

    private enum Phase {
        case checking
        case chooseBackend
        case downloading
        case configuringOllama
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

            case .chooseBackend:
                ScrollView {
                    VStack(spacing: 20) {
                        Image(systemName: "cpu")
                            .font(.system(size: 44))
                            .foregroundStyle(.secondary)
                            .padding(.top, 8)

                        Text("Longview Health uses a local AI model to extract lab results, imaging findings, and other medical data from your documents. Everything runs on your Mac -- no data leaves your machine.")
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)

                        // Option 1: Download recommended model
                        VStack(spacing: 6) {
                            Button {
                                phase = .downloading
                                Task { await startDownload() }
                            } label: {
                                VStack(spacing: 4) {
                                    Text("Download Recommended Model")
                                    Text("Qwen 2.5 3B Instruct (4-bit) -- ~2 GB, one-time download")
                                        .font(.caption2)
                                        .foregroundStyle(.white.opacity(0.7))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 4)
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.large)

                            Text("Best option if you don't have a local LLM set up already.")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        }

                        dividerWithText("or")

                        // Option 2: Use existing Ollama
                        VStack(spacing: 8) {
                            HStack(spacing: 8) {
                                Text("Already running Ollama?")
                                    .font(.callout.weight(.medium))
                                if ollamaChecking {
                                    ProgressView()
                                        .controlSize(.small)
                                } else if ollamaAvailable {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(.green)
                                        .font(.callout)
                                }
                            }

                            if ollamaAvailable {
                                Button("Use Ollama") {
                                    phase = .configuringOllama
                                    Task { await switchToOllama() }
                                }
                                .controlSize(.large)
                                Text("Detected Ollama at localhost:11434")
                                    .font(.caption)
                                    .foregroundStyle(.green)
                            } else if !ollamaChecking {
                                Text("No Ollama server detected at localhost:11434. Start Ollama and reopen this dialog, or download the recommended model above.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .multilineTextAlignment(.center)
                                Button("Check Again") {
                                    Task { await checkOllama() }
                                }
                                .font(.caption)
                            }
                        }
                        .padding()
                        .background(.background.secondary)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .padding(28)
                }

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

            case .configuringOllama:
                Spacer()
                ProgressView("Switching to Ollama backend...")
                Spacer()

            case .done:
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(.green)
                    Text("Ready!")
                        .font(.title3.weight(.medium))
                }
                Spacer()

            case .error(let message):
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 48))
                        .foregroundStyle(.orange)
                    Text("Something went wrong")
                        .font(.title3.weight(.medium))
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Button("Try Again") {
                        phase = .chooseBackend
                        lines = []
                    }
                }
                Spacer()
            }
        }
        .frame(minWidth: 500, idealWidth: 540, minHeight: 400, idealHeight: 480)
        .task { await checkStatus() }
    }

    private var subtitle: String {
        switch phase {
        case .checking: return "Checking..."
        case .chooseBackend: return "Setup"
        case .downloading: return "Downloading..."
        case .configuringOllama: return "Configuring..."
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
        default:
            EmptyView()
        }
    }

    private func dividerWithText(_ text: String) -> some View {
        HStack {
            Rectangle().frame(height: 1).foregroundStyle(.separator)
            Text(text)
                .font(.caption)
                .foregroundStyle(.tertiary)
            Rectangle().frame(height: 1).foregroundStyle(.separator)
        }
    }

    // MARK: - Actions

    private func checkStatus() async {
        let (isDownloaded, _) = await CLIRunner.shared.modelStatus()
        if isDownloaded {
            isPresented = false
        } else {
            // Also probe for Ollama in the background
            phase = .chooseBackend
            await checkOllama()
        }
    }

    private func checkOllama() async {
        ollamaChecking = true
        defer { ollamaChecking = false }

        // Quick probe: try to hit Ollama's API
        var available = false
        for await line in CLIRunner.shared.run(arguments: ["settings", "get", "ollama_url"]) {
            // We got a response, CLI is working. Now check if Ollama is actually running.
            _ = line
        }

        // Use a URLSession probe to check if Ollama is reachable
        if let url = URL(string: "http://localhost:11434/api/tags") {
            do {
                let (_, response) = try await URLSession.shared.data(from: url)
                if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                    available = true
                }
            } catch {
                // Not reachable
            }
        }

        await MainActor.run {
            ollamaAvailable = available
        }
    }

    private func switchToOllama() async {
        // Set the backend to ollama via CLI
        var success = false
        for await line in CLIRunner.shared.run(arguments: ["settings", "set", "llm_backend", "ollama"]) {
            if line.contains("Set llm_backend") {
                success = true
            }
        }
        if success {
            phase = .done
        } else {
            phase = .error("Failed to configure Ollama backend.")
        }
    }

    private func startDownload() async {
        for await line in CLIRunner.shared.modelDownload() {
            lines.append(line)
        }
        let (isDownloaded, _) = await CLIRunner.shared.modelStatus()
        if isDownloaded {
            phase = .done
        } else {
            let lastError = lines.last { $0.hasPrefix("[error]") } ?? "Unknown error"
            phase = .error(lastError)
        }
    }
}
