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
                    "All Clear",
                    systemImage: "checkmark.seal",
                    description: Text("Every result has been reviewed.")
                )
            } else {
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(items) { item in
                            ReviewCard(
                                item: item,
                                isProcessing: isProcessing,
                                onAccept: { Task { await acceptItem(item) } },
                                onReject: { Task { await rejectItem(item) } }
                            )
                        }
                    }
                    .padding(20)
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

private struct ReviewCard: View {
    let item: ReviewItem
    let isProcessing: Bool
    let onAccept: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(item.testName)
                    .font(.body.weight(.semibold))
                Spacer()
                Text(item.formattedDate)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(item.reason)
                .font(.callout)
                .foregroundStyle(.secondary)
                .lineLimit(3)

            HStack {
                Spacer()

                Button(action: onReject) {
                    Label("Reject", systemImage: "xmark")
                        .font(.callout)
                }
                .buttonStyle(.bordered)
                .tint(Theme.critical)
                .controlSize(.small)
                .disabled(isProcessing)

                Button(action: onAccept) {
                    Label("Accept", systemImage: "checkmark")
                        .font(.callout)
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.positive)
                .controlSize(.small)
                .disabled(isProcessing)
            }
        }
        .cardStyle()
    }
}
