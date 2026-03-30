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
    .frame(width: 700, height: 560)
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
            VStack(alignment: .leading, spacing: 20) {
                // Summary cards
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                ], spacing: 12) {
                    SummaryCard(
                        title: "Documents",
                        value: "\(documentCount)",
                        systemImage: "doc.on.doc",
                        color: Theme.accent
                    )
                    SummaryCard(
                        title: "Results",
                        value: "\(resultCount)",
                        systemImage: "list.bullet.clipboard",
                        color: Theme.positive
                    )
                    SummaryCard(
                        title: "Pending Review",
                        value: "\(pendingReviewCount)",
                        systemImage: "checkmark.circle",
                        color: pendingReviewCount > 0 ? Theme.attention : .secondary
                    )
                }

                // Date range
                if let range = dateRange {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Date Range", systemImage: "calendar")
                            .font(Theme.sectionHeaderFont)
                            .foregroundStyle(.secondary)

                        HStack(spacing: 12) {
                            Text(formatDateString(range.earliest))
                                .font(.body.weight(.medium))
                            Image(systemName: "arrow.right")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                            Text(formatDateString(range.latest))
                                .font(.body.weight(.medium))
                            Spacer()
                        }
                        .padding(14)
                        .cardStyle(padding: 0)
                        .padding(.horizontal, 14)
                    }
                }

                // Results by category
                if !categoryCounts.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Results by Category", systemImage: "square.stack.3d.up")
                            .font(Theme.sectionHeaderFont)
                            .foregroundStyle(.secondary)

                        VStack(spacing: 0) {
                            ForEach(Array(sortedCategories.enumerated()), id: \.element.category) { index, item in
                                HStack(spacing: 12) {
                                    Image(systemName: item.category.systemImage)
                                        .font(.body)
                                        .foregroundStyle(Theme.accent)
                                        .frame(width: 24)
                                    Text(item.category.displayName)
                                        .font(.body)
                                    Spacer()
                                    Text("\(item.count)")
                                        .font(.body.monospacedDigit().weight(.medium))
                                        .foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 10)
                                .padding(.horizontal, 14)

                                if index < sortedCategories.count - 1 {
                                    Divider()
                                        .padding(.leading, 50)
                                }
                            }
                        }
                        .cardStyle(padding: 0)
                    }
                }
            }
            .padding(24)
        }
        .navigationTitle("Dashboard")
        .task { loadData() }
    }

    private var sortedCategories: [(category: ResultCategory, count: Int)] {
        ResultCategory.allCases.compactMap { cat in
            guard let count = categoryCounts[cat], count > 0 else { return nil }
            return (category: cat, count: count)
        }
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
    var color: Color = Theme.accent

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.title2)
                .foregroundStyle(color)

            Text(value)
                .font(Theme.metricFont)
                .monospacedDigit()
                .foregroundStyle(.primary)

            Text(title)
                .font(Theme.captionFont)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .cardStyle()
    }
}
