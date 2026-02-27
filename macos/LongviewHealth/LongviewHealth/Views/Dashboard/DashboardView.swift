import SwiftUI

#Preview {
    NavigationStack {
        DashboardView(
            documentCount: 12,
            resultCount: 47,
            pendingReviewCount: 3,
            categoryCounts: [.lab: 38, .imaging: 5, .vital: 4],
            dateRange: (earliest: "2023-06-14", latest: "2025-01-15")
        )
    }
    .frame(width: 600, height: 500)
}

struct DashboardView: View {
    let database: VaultDatabase?

    @State private var documentCount: Int
    @State private var resultCount: Int
    @State private var pendingReviewCount: Int
    @State private var categoryCounts: [ResultCategory: Int]
    @State private var dateRange: (earliest: String, latest: String)?

    /// Production init -- loads from database.
    init(database: VaultDatabase) {
        self.database = database
        _documentCount = State(initialValue: 0)
        _resultCount = State(initialValue: 0)
        _pendingReviewCount = State(initialValue: 0)
        _categoryCounts = State(initialValue: [:])
        _dateRange = State(initialValue: nil)
    }

    /// Preview init -- static data, no database.
    fileprivate init(
        documentCount: Int,
        resultCount: Int,
        pendingReviewCount: Int,
        categoryCounts: [ResultCategory: Int],
        dateRange: (earliest: String, latest: String)?
    ) {
        self.database = nil
        _documentCount = State(initialValue: documentCount)
        _resultCount = State(initialValue: resultCount)
        _pendingReviewCount = State(initialValue: pendingReviewCount)
        _categoryCounts = State(initialValue: categoryCounts)
        _dateRange = State(initialValue: dateRange)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Summary cards
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                ], spacing: 16) {
                    SummaryCard(
                        title: "Documents",
                        value: "\(documentCount)",
                        systemImage: "doc.on.doc"
                    )
                    SummaryCard(
                        title: "Results",
                        value: "\(resultCount)",
                        systemImage: "list.bullet.clipboard"
                    )
                    SummaryCard(
                        title: "Pending Review",
                        value: "\(pendingReviewCount)",
                        systemImage: "checkmark.circle",
                        highlight: pendingReviewCount > 0
                    )
                }

                // Date range
                if let range = dateRange {
                    GroupBox("Date Range") {
                        HStack {
                            Text(formatDateString(range.earliest))
                            Image(systemName: "arrow.right")
                                .foregroundStyle(.secondary)
                            Text(formatDateString(range.latest))
                            Spacer()
                        }
                        .font(.body)
                        .padding(.top, 4)
                    }
                }

                // Results by category
                if !categoryCounts.isEmpty {
                    GroupBox("Results by Category") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(ResultCategory.allCases, id: \.self) { cat in
                                if let count = categoryCounts[cat], count > 0 {
                                    HStack {
                                        Image(systemName: cat.systemImage)
                                            .frame(width: 20)
                                            .foregroundStyle(.secondary)
                                        Text(cat.displayName)
                                        Spacer()
                                        Text("\(count)")
                                            .foregroundStyle(.secondary)
                                            .monospacedDigit()
                                    }
                                }
                            }
                        }
                        .padding(.top, 4)
                    }
                }
            }
            .padding(24)
        }
        .navigationTitle("Dashboard")
        .task { loadData() }
    }

    private func loadData() {
        guard let database else { return }
        documentCount = (try? database.documentCount()) ?? 0
        resultCount = (try? database.resultCount()) ?? 0
        pendingReviewCount = (try? database.pendingReviewCount()) ?? 0
        categoryCounts = (try? database.resultCountsByCategory()) ?? [:]
        dateRange = try? database.dateRange()
    }

    private func formatDateString(_ iso: String) -> String {
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

/// A single summary metric card.
private struct SummaryCard: View {
    let title: String
    let value: String
    let systemImage: String
    var highlight: Bool = false

    var body: some View {
        GroupBox {
            VStack(spacing: 8) {
                Image(systemName: systemImage)
                    .font(.title2)
                    .foregroundStyle(highlight ? .red : .accentColor)
                Text(value)
                    .font(.system(.title, design: .rounded, weight: .semibold))
                    .monospacedDigit()
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
        }
    }
}
