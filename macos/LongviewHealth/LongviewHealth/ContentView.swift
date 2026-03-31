import SwiftUI

struct ContentView: View {
    @State private var selectedSection: SidebarSection = .dashboard
    @State private var selectedVault: DiscoveredVault?
    @State private var vaults: [DiscoveredVault] = []
    @State private var database: VaultDatabase?
    @State private var showingProcessing = false
    @State private var showingCreateVault = false
    @State private var showingModelManager = false
    @State private var pendingReviewCount = 0
    @State private var hasCheckedModel = false

    var body: some View {
        NavigationSplitView {
            SidebarView(
                selectedSection: $selectedSection,
                selectedVault: $selectedVault,
                vaults: vaults,
                pendingReviewCount: pendingReviewCount,
                onScan: { startScan() },
                onExport: { startExport() },
                onCreateVault: { showingCreateVault = true }
            )
        } detail: {
            if let database, let vault = selectedVault {
                Group {
                    switch selectedSection {
                    case .dashboard:
                        DashboardView(database: database)
                    case .results:
                        ResultsView(database: database)
                    case .trends:
                        TrendListView(database: database)
                    case .documents:
                        DocumentsListView(database: database)
                    case .review:
                        ReviewView(database: database, vaultName: vault.name)
                    }
                }
                .id(vault.name)
            } else {
                ContentUnavailableView(
                    "No Vault Selected",
                    systemImage: "tray",
                    description: Text("Select a vault from the sidebar to get started.")
                )
            }
        }
        .sheet(isPresented: $showingProcessing) {
            if let vault = selectedVault {
                ProcessingView(vaultName: vault.name, isPresented: $showingProcessing)
            }
        }
        .sheet(isPresented: $showingCreateVault) {
            CreateVaultView { name in
                refreshVaults()
                selectedVault = vaults.first { $0.name == name }
            }
        }
        .sheet(isPresented: $showingModelManager) {
            ModelManagerView(isPresented: $showingModelManager)
        }
        .onAppear {
            refreshVaults()
            checkModelOnFirstLaunch()
        }
        .onChange(of: selectedVault) { _, newVault in
            openVault(newVault)
        }
    }

    private func refreshVaults() {
        vaults = VaultDiscovery.discoverVaults()
        if selectedVault == nil {
            selectedVault = vaults.first
        }
    }

    private func openVault(_ vault: DiscoveredVault?) {
        guard let vault else {
            database = nil
            return
        }
        do {
            database = try VaultDatabase(path: vault.dbPath)
            observeReviewCount()
        } catch {
            database = nil
        }
    }

    private func observeReviewCount() {
        guard let database else { return }
        let observation = database.observePendingReviewCount()
        Task {
            for try await count in observation.values(in: database.dbPool) {
                await MainActor.run {
                    pendingReviewCount = count
                }
            }
        }
    }

    private func checkModelOnFirstLaunch() {
        guard !hasCheckedModel else { return }
        hasCheckedModel = true
        Task {
            let (isDownloaded, _) = await CLIRunner.shared.modelStatus()
            if !isDownloaded {
                await MainActor.run { showingModelManager = true }
            }
        }
    }

    private func startScan() {
        showingProcessing = true
    }

    private func startExport() {
        guard let vault = selectedVault else { return }
        Task {
            _ = try? await CLIRunner.shared.runExport(vaultName: vault.name)
        }
    }
}

/// Simple list of documents -- used for the Documents sidebar section.
struct DocumentsListView: View {
    let database: VaultDatabase
    @State private var documents: [Document] = []
    @State private var resultCounts: [String: Int] = [:]

    private var totalResults: Int {
        resultCounts.values.reduce(0, +)
    }

    private var docsWithResults: Int {
        documents.filter { (resultCounts[$0.id] ?? 0) > 0 }.count
    }

    var body: some View {
        Group {
            if documents.isEmpty {
                ContentUnavailableView(
                    "No Documents",
                    systemImage: "doc.on.doc",
                    description: Text("Scan a vault to import documents.")
                )
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        // Coverage summary
                        HStack(spacing: 16) {
                            Label("\(documents.count) documents", systemImage: "doc.on.doc")
                            Label("\(totalResults) results", systemImage: "list.bullet.clipboard")
                            if docsWithResults < documents.count {
                                Label(
                                    "\(documents.count - docsWithResults) with no results",
                                    systemImage: "exclamationmark.triangle"
                                )
                                .foregroundStyle(Theme.attention)
                            }
                        }
                        .font(Theme.captionFont)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 4)

                        ForEach(documents) { doc in
                            let count = resultCounts[doc.id] ?? 0
                            HStack(spacing: 12) {
                                Image(systemName: count > 0 ? "doc.fill" : "doc.badge.ellipsis")
                                    .font(.title3)
                                    .foregroundStyle(count > 0 ? Theme.accent : Theme.attention)
                                    .frame(width: 28)

                                VStack(alignment: .leading, spacing: 3) {
                                    Text(doc.filename)
                                        .font(.body.weight(.medium))
                                        .lineLimit(1)
                                    HStack(spacing: 10) {
                                        Text(doc.documentType.uppercased())
                                            .font(.caption.weight(.medium))
                                            .foregroundStyle(Theme.accent)
                                        if let pages = doc.pageCount {
                                            Text("\(pages) page\(pages == 1 ? "" : "s")")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Text("\(count) result\(count == 1 ? "" : "s")")
                                            .font(.caption.weight(.medium))
                                            .foregroundStyle(count > 0 ? Theme.positive : Theme.attention)
                                    }
                                }
                                Spacer()

                                Text(formatIngestedDate(doc.ingestedAt))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .cardStyle()
                            .onTapGesture(count: 2) {
                                openDocument(doc)
                            }
                        }
                    }
                    .padding(20)
                }
            }
        }
        .navigationTitle("Documents")
        .task { loadDocuments() }
    }

    private func loadDocuments() {
        documents = (try? database.fetchDocuments()) ?? []
        resultCounts = (try? database.resultCountsByDocument()) ?? [:]
    }

    private func openDocument(_ doc: Document) {
        let url = URL(fileURLWithPath: doc.filePath)
        NSWorkspace.shared.open(url)
    }

    private func formatIngestedDate(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        if let date = formatter.date(from: String(iso.prefix(10))) {
            let display = DateFormatter()
            display.dateStyle = .medium
            return display.string(from: date)
        }
        return String(iso.prefix(10))
    }
}
