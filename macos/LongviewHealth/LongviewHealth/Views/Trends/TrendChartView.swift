import SwiftUI
import Charts

struct TrendChartView: View {
    let database: VaultDatabase
    let testName: String

    @State private var results: [MedicalResult] = []

    /// Points with parseable numeric values and dates.
    private var chartPoints: [(date: Date, value: Double, isAbnormal: Bool)] {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        return results.compactMap { result in
            guard let value = result.numericValue,
                  let date = formatter.date(from: String(result.resultDate.prefix(10))) else {
                return nil
            }
            return (date: date, value: value, isAbnormal: result.isAbnormal ?? false)
        }
    }

    /// Reference range bounds (from the first result that has them).
    private var referenceBounds: (low: Double, high: Double)? {
        for result in results {
            if let lowStr = result.referenceLow, let highStr = result.referenceHigh,
               let low = Double(lowStr), let high = Double(highStr) {
                return (low, high)
            }
        }
        return nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(testName)
                    .font(.title3.weight(.semibold))
                if let unit = results.first?.unit {
                    Text("(\(unit))")
                        .font(.body)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text("\(chartPoints.count) data points")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if chartPoints.isEmpty {
                ContentUnavailableView(
                    "No Numeric Data",
                    systemImage: "chart.xyaxis.line",
                    description: Text("This test has no numeric values to chart.")
                )
            } else {
                Chart {
                    // Reference range shaded band
                    if let bounds = referenceBounds {
                        RectangleMark(
                            yStart: .value("Low", bounds.low),
                            yEnd: .value("High", bounds.high)
                        )
                        .foregroundStyle(.green.opacity(0.08))
                    }

                    // Line connecting points
                    ForEach(chartPoints, id: \.date) { point in
                        LineMark(
                            x: .value("Date", point.date),
                            y: .value("Value", point.value)
                        )
                        .foregroundStyle(Color.accentColor)
                        .interpolationMethod(.catmullRom)
                    }

                    // Individual data points
                    ForEach(chartPoints, id: \.date) { point in
                        PointMark(
                            x: .value("Date", point.date),
                            y: .value("Value", point.value)
                        )
                        .foregroundStyle(point.isAbnormal ? .red : .accentColor)
                        .symbolSize(point.isAbnormal ? 60 : 40)
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading)
                }
                .chartXAxis {
                    AxisMarks(values: .automatic) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                    }
                }
                .frame(minHeight: 300)
            }

            // Data table below chart
            if !results.isEmpty {
                GroupBox("History") {
                    Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 6) {
                        GridRow {
                            Text("Date").font(.caption.weight(.medium))
                            Text("Value").font(.caption.weight(.medium))
                            Text("Ref Range").font(.caption.weight(.medium))
                            Text("Flag").font(.caption.weight(.medium))
                        }
                        .foregroundStyle(.secondary)

                        Divider()

                        ForEach(results) { result in
                            GridRow {
                                Text(result.formattedDate)
                                    .font(.body)
                                HStack(spacing: 2) {
                                    Text(result.value)
                                        .monospacedDigit()
                                    if let unit = result.unit {
                                        Text(unit)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                Text(result.referenceRange ?? "--")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                if result.isAbnormal == true {
                                    Text("abnormal")
                                        .font(.caption)
                                        .foregroundStyle(.red)
                                } else {
                                    Text("")
                                }
                            }
                        }
                    }
                    .padding(.top, 4)
                }
            }
        }
        .padding(24)
        .task(id: testName) { loadResults() }
    }

    private func loadResults() {
        results = (try? database.fetchResultsForTest(testName)) ?? []
    }
}
