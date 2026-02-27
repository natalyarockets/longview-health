import SwiftUI

struct SidebarView: View {
    @Binding var selectedSection: SidebarSection
    @Binding var selectedVault: DiscoveredVault?
    let vaults: [DiscoveredVault]
    let pendingReviewCount: Int
    let onScan: () -> Void
    let onExport: () -> Void
    let onCreateVault: () -> Void

    var body: some View {
        List(selection: $selectedSection) {
            Section {
                HStack {
                    Picker("Vault", selection: $selectedVault) {
                        Text("Select a vault...")
                            .tag(nil as DiscoveredVault?)
                        ForEach(vaults) { vault in
                            Text(vault.displayName)
                                .tag(vault as DiscoveredVault?)
                        }
                    }
                    .labelsHidden()

                    Button(action: onCreateVault) {
                        Image(systemName: "plus")
                    }
                    .buttonStyle(.borderless)
                    .help("Create a new vault")
                }
            }

            Section {
                ForEach(SidebarSection.allCases) { section in
                    Label {
                        HStack {
                            Text(section.displayName)
                            Spacer()
                            if section == .review && pendingReviewCount > 0 {
                                Text("\(pendingReviewCount)")
                                    .font(.caption2.weight(.medium))
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(.red.opacity(0.15))
                                    .foregroundStyle(.red)
                                    .clipShape(Capsule())
                            }
                        }
                    } icon: {
                        Image(systemName: section.systemImage)
                    }
                    .tag(section)
                }
            }
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: 12) {
                Button(action: onScan) {
                    Label("Scan", systemImage: "arrow.clockwise")
                }
                .disabled(selectedVault == nil)

                Button(action: onExport) {
                    Label("Export", systemImage: "square.and.arrow.up")
                }
                .disabled(selectedVault == nil)

                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .navigationSplitViewColumnWidth(min: 200, ideal: 220, max: 280)
    }
}
