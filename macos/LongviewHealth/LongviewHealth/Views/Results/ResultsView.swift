import SwiftUI

struct ResultsView: View {
    let database: VaultDatabase

    @State private var results: [MedicalResult] = []
    @State private var selectedCategory: ResultCategory?
    @State private var searchText = ""
    @State private var selectedResultID: MedicalResult.ID?
    @State private var showingDetail = false
    @State private var sortOrder = [KeyPathComparator(\MedicalResult.resultDate, order: .reverse)]

    private var filteredResults: [MedicalResult] {
        var filtered = results

        if let category = selectedCategory {
            filtered = filtered.filter { $0.category == category }
        }

        if !searchText.isEmpty {
            let query = searchText.lowercased()
            filtered = filtered.filter {
                $0.testName.lowercased().contains(query)
            }
        }

        return filtered.sorted(using: sortOrder)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Filters toolbar
            HStack(spacing: 12) {
                Picker("Category", selection: $selectedCategory) {
                    Text("All Categories")
                        .tag(nil as ResultCategory?)
                    ForEach(ResultCategory.allCases) { cat in
                        Label(cat.displayName, systemImage: cat.systemImage)
                            .tag(cat as ResultCategory?)
                    }
                }
                .frame(width: 170)

                TextField("Search tests...", text: $searchText)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 220)

                Spacer()

                Text("\(filteredResults.count) results")
                    .font(Theme.captionFont)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)

            Divider()

            // Results table
            Table(filteredResults, selection: $selectedResultID, sortOrder: $sortOrder) {
                TableColumn("Date", value: \.resultDate) { result in
                    Text(result.formattedDate)
                        .font(.body)
                }
                .width(min: 80, ideal: 100)

                TableColumn("Test", value: \.testName) { result in
                    Text(result.testName)
                        .font(.body)
                }
                .width(min: 120, ideal: 200)

                TableColumn("Value", value: \.value) { result in
                    HStack(spacing: 4) {
                        Text(result.value)
                            .font(.body.monospacedDigit())
                        if let unit = result.unit {
                            Text(unit)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .width(min: 80, ideal: 100)

                TableColumn("Ref Range") { result in
                    if let range = result.referenceRange {
                        Text(range)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("--")
                            .foregroundStyle(.quaternary)
                    }
                }
                .width(min: 80, ideal: 100)

                TableColumn("Flag") { result in
                    if result.isAbnormal == true {
                        StatusBadge("Abnormal")
                    }
                }
                .width(min: 70, ideal: 90)

                TableColumn("Category", value: \.category.rawValue) { result in
                    Label(result.category.displayName, systemImage: result.category.systemImage)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .width(min: 80, ideal: 100)
            }
        }
        .navigationTitle("Results")
        .onChange(of: selectedResultID) { _, newID in
            showingDetail = newID != nil
        }
        .sheet(isPresented: $showingDetail, onDismiss: { selectedResultID = nil }) {
            if let id = selectedResultID,
               let result = filteredResults.first(where: { $0.id == id }) {
                ResultDetailView(result: result)
            }
        }
        .task { loadResults() }
    }

    private func loadResults() {
        results = (try? database.fetchResults()) ?? []
    }
}
