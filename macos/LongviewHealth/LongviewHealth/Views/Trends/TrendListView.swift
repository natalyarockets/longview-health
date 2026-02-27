import SwiftUI

struct TrendListView: View {
    let database: VaultDatabase

    @State private var testsByCategory: [(category: ResultCategory, tests: [String])] = []
    @State private var selectedTest: String?

    var body: some View {
        HSplitView {
            // Left: test list grouped by category
            List(selection: $selectedTest) {
                ForEach(testsByCategory, id: \.category) { group in
                    Section(group.category.displayName) {
                        ForEach(group.tests, id: \.self) { test in
                            Text(test)
                                .tag(test)
                        }
                    }
                }
            }
            .listStyle(.sidebar)
            .frame(minWidth: 180, idealWidth: 220, maxWidth: 280)

            // Right: chart for selected test
            if let test = selectedTest {
                TrendChartView(database: database, testName: test)
            } else {
                ContentUnavailableView(
                    "Select a Test",
                    systemImage: "chart.xyaxis.line",
                    description: Text("Choose a test from the list to see its trend over time.")
                )
            }
        }
        .navigationTitle("Trends")
        .task { loadTests() }
    }

    private func loadTests() {
        testsByCategory = (try? database.testsByCategory()) ?? []
    }
}
