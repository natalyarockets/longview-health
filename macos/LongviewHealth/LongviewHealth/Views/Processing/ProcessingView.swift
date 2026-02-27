import SwiftUI

/// Modal sheet shown during CLI operations (rescan, export).
/// Streams stdout from the CLI process in real time.
struct ProcessingView: View {
    let vaultName: String
    @Binding var isPresented: Bool

    @State private var lines: [String] = []
    @State private var isRunning = true

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text("Scanning \(vaultName)...")
                    .font(.title3.weight(.semibold))
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

            Divider()

            // Log output
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
        }
        .frame(minWidth: 500, idealWidth: 600, minHeight: 350, idealHeight: 400)
        .task { await runScan() }
    }

    private func runScan() async {
        for await line in CLIRunner.shared.runRescan(vaultName: vaultName) {
            lines.append(line)
        }
        isRunning = false
    }
}
