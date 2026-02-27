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
            if let database {
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
                    ReviewView(database: database, vaultName: selectedVault?.name ?? "")
                }
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

    var body: some View {
        List(documents) { doc in
            VStack(alignment: .leading, spacing: 4) {
                Text(doc.filename)
                    .font(.body)
                HStack(spacing: 12) {
                    Text(doc.documentType.uppercased())
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if let pages = doc.pageCount {
                        Text("\(pages) page\(pages == 1 ? "" : "s")")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Text(doc.ingestedAt.prefix(10))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 2)
        }
        .navigationTitle("Documents")
        .task { loadDocuments() }
    }

    private func loadDocuments() {
        documents = (try? database.fetchDocuments()) ?? []
    }
}
