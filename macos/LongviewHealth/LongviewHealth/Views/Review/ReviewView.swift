import SwiftUI

struct ReviewView: View {
    let database: VaultDatabase
    let vaultName: String

    @State private var items: [ReviewItem] = []
    @State private var selectedItem: ReviewItem?
    @State private var isProcessing = false

    var body: some View {
        Group {
            if items.isEmpty {
                ContentUnavailableView(
                    "No Pending Reviews",
                    systemImage: "checkmark.circle",
                    description: Text("All items have been reviewed.")
                )
            } else {
                List(items, selection: $selectedItem) { item in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(item.testName)
                                .font(.body.weight(.medium))
                            Spacer()
                            Text(item.formattedDate)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Text(item.reason)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)

                        HStack(spacing: 8) {
                            Text("Doc: \(String(item.documentId.prefix(8)))...")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)

                            Spacer()

                            Button("Accept") {
                                Task { await acceptItem(item) }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(.green)
                            .controlSize(.small)
                            .disabled(isProcessing)

                            Button("Reject") {
                                Task { await rejectItem(item) }
                            }
                            .buttonStyle(.bordered)
                            .tint(.red)
                            .controlSize(.small)
                            .disabled(isProcessing)
                        }
                    }
                    .padding(.vertical, 4)
                    .tag(item)
                }
            }
        }
        .navigationTitle("Review Queue")
        .task { loadItems() }
    }

    private func loadItems() {
        items = (try? database.fetchPendingReviews()) ?? []
    }

    private func acceptItem(_ item: ReviewItem) async {
        isProcessing = true
        defer { isProcessing = false }
        _ = try? await CLIRunner.shared.reviewAccept(vaultName: vaultName, reviewId: item.id)
        loadItems()
    }

    private func rejectItem(_ item: ReviewItem) async {
        isProcessing = true
        defer { isProcessing = false }
        _ = try? await CLIRunner.shared.reviewReject(vaultName: vaultName, reviewId: item.id)
        loadItems()
    }
}
