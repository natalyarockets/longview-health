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
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                HStack(alignment: .firstTextBaseline) {
                    Text(testName)
                        .font(Theme.largeTitleFont)
                    if let unit = results.first?.unit {
                        Text("(\(unit))")
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(chartPoints.count) data points")
                        .font(Theme.captionFont)
                        .foregroundStyle(.secondary)
                }

                if chartPoints.isEmpty {
                    ContentUnavailableView(
                        "No Numeric Data",
                        systemImage: "chart.xyaxis.line",
                        description: Text("This test has no numeric values to chart.")
                    )
                } else {
                    // Chart
                    Chart {
                        // Reference range shaded band
                        if let bounds = referenceBounds {
                            RectangleMark(
                                yStart: .value("Low", bounds.low),
                                yEnd: .value("High", bounds.high)
                            )
                            .foregroundStyle(Theme.referenceRangeFill)
                        }

                        // Line connecting points
                        ForEach(chartPoints, id: \.date) { point in
                            LineMark(
                                x: .value("Date", point.date),
                                y: .value("Value", point.value)
                            )
                            .foregroundStyle(Theme.accent)
                            .interpolationMethod(.catmullRom)
                            .lineStyle(StrokeStyle(lineWidth: 2.5))
                        }

                        // Individual data points
                        ForEach(chartPoints, id: \.date) { point in
                            PointMark(
                                x: .value("Date", point.date),
                                y: .value("Value", point.value)
                            )
                            .foregroundStyle(point.isAbnormal ? Theme.attention : Theme.accent)
                            .symbolSize(point.isAbnormal ? 70 : 50)
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
                    .cardStyle()

                    // Data table below chart
                    if !results.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("History")
                                .font(Theme.sectionHeaderFont)
                                .foregroundStyle(.secondary)

                            VStack(spacing: 0) {
                                // Header row
                                HStack {
                                    Text("Date")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text("Value")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text("Ref Range")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                    Text("Flag")
                                        .frame(width: 80, alignment: .leading)
                                }
                                .font(.caption.weight(.medium))
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)

                                Divider()

                                ForEach(results) { result in
                                    HStack {
                                        Text(result.formattedDate)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                        HStack(spacing: 2) {
                                            Text(result.value)
                                                .monospacedDigit()
                                            if let unit = result.unit {
                                                Text(unit)
                                                    .font(.caption)
                                                    .foregroundStyle(.secondary)
                                            }
                                        }
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        Text(result.referenceRange ?? "--")
                                            .font(.callout)
                                            .foregroundStyle(.secondary)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                        Group {
                                            if result.isAbnormal == true {
                                                StatusBadge("Abnormal")
                                            } else {
                                                Text("")
                                            }
                                        }
                                        .frame(width: 80, alignment: .leading)
                                    }
                                    .font(.callout)
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 8)
                                }
                            }
                            .cardStyle(padding: 0)
                        }
                    }
                }
            }
            .padding(24)
        }
        .task(id: testName) { loadResults() }

        Divider()
            .padding(.top, 8)
    }

    private func loadResults() {
        results = (try? database.fetchResultsForTest(testName)) ?? []
    }
}
