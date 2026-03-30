import SwiftUI

struct TrendListView: View {
    let database: VaultDatabase

    @State private var testsByCategory: [(category: ResultCategory, tests: [String])] = []
    @State private var selectedTest: String?
    @State private var allResults: [String: [MedicalResult]] = [:]

    var body: some View {
        HStack(spacing: 0) {
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
            .frame(width: 220)

            Divider()

            // Right: all test charts in a scrollable view
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 32) {
                        ForEach(testsByCategory, id: \.category) { group in
                            ForEach(group.tests, id: \.self) { test in
                                TrendChartView(
                                    database: database,
                                    testName: test
                                )
                                .id(test)
                            }
                        }
                    }
                    .padding(.bottom, 24)
                }
                .onChange(of: selectedTest) { _, newTest in
                    guard let test = newTest else { return }
                    withAnimation {
                        proxy.scrollTo(test, anchor: .top)
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle("Trends")
        .task { loadTests() }
    }

    private func loadTests() {
        testsByCategory = (try? database.testsByCategory()) ?? []
    }
}
