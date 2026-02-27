import SwiftUI

/// Sheet for creating a new vault via the CLI.
struct CreateVaultView: View {
    var onCreated: (String) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var documentsPath = ""
    @State private var useExistingFolder = false
    @State private var isCreating = false
    @State private var errorMessage: String?

    private var sanitizedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: " ", with: "-")
    }

    private var isValid: Bool {
        !sanitizedName.isEmpty && (!useExistingFolder || !documentsPath.isEmpty)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text("New Vault")
                    .font(.title3.weight(.semibold))
                Spacer()
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
            }
            .padding(20)

            Divider()

            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Name")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("e.g. alice, dad", text: $name)
                        .textFieldStyle(.roundedBorder)
                    if !sanitizedName.isEmpty && sanitizedName != name {
                        Text("Will be created as: \(sanitizedName)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Toggle("Point to an existing documents folder", isOn: $useExistingFolder)

                if useExistingFolder {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Documents Folder")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        HStack {
                            TextField("/path/to/documents", text: $documentsPath)
                                .textFieldStyle(.roundedBorder)
                            Button("Choose...") { pickFolder() }
                        }
                    }
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }
            .padding(20)

            Spacer()

            Divider()

            HStack {
                Spacer()
                Button("Create") {
                    Task { await createVault() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(!isValid || isCreating)
                .keyboardShortcut(.defaultAction)
            }
            .padding(20)
        }
        .frame(width: 400, height: useExistingFolder ? 320 : 260)
    }

    private func pickFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.message = "Select the folder containing medical documents"
        if panel.runModal() == .OK, let url = panel.url {
            documentsPath = url.path
        }
    }

    private func createVault() async {
        isCreating = true
        errorMessage = nil

        let path = useExistingFolder ? documentsPath : nil
        let output = await CLIRunner.shared.createVault(name: sanitizedName, documentsPath: path)
        let joined = output.joined(separator: "\n")

        if joined.lowercased().contains("error") {
            errorMessage = joined
            isCreating = false
        } else {
            onCreated(sanitizedName)
            dismiss()
        }
    }
}
