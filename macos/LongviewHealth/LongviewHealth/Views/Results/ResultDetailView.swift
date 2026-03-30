import SwiftUI

struct ResultDetailView: View {
    let result: MedicalResult
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(result.testName)
                        .font(Theme.largeTitleFont)
                    Text(result.category.displayName)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") { dismiss() }
                    .keyboardShortcut(.cancelAction)
            }
            .padding(20)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Value highlight
                    HStack(spacing: 8) {
                        Text(result.value)
                            .font(.system(.title, design: .rounded, weight: .semibold))
                            .monospacedDigit()
                        if let unit = result.unit {
                            Text(unit)
                                .font(.title3)
                                .foregroundStyle(.secondary)
                        }
                        if result.isAbnormal == true {
                            StatusBadge("Abnormal")
                        }
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        result.isAbnormal == true
                            ? Theme.attentionTint
                            : Theme.accentTint
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    // Detail rows
                    VStack(spacing: 0) {
                        if let range = result.referenceRange {
                            DetailRow(label: "Reference Range", value: range)
                            Divider().padding(.leading, 120)
                        }
                        DetailRow(label: "Date", value: result.formattedDate)
                        Divider().padding(.leading, 120)
                        DetailRow(label: "Confidence", value: result.confidence.rawValue.capitalized)
                        Divider().padding(.leading, 120)
                        DetailRow(label: "Validation", value: result.validationStatus.rawValue.capitalized)
                        Divider().padding(.leading, 120)
                        DetailRow(label: "Extractor", value: "v\(result.extractorVersion) (\(result.parserUsed))")

                        if let notes = result.notes, !notes.isEmpty {
                            Divider().padding(.leading, 120)
                            DetailRow(label: "Notes", value: notes)
                        }
                    }
                }
                .padding(20)
            }
        }
        .frame(minWidth: 420, idealWidth: 480, minHeight: 380)
    }
}

private struct DetailRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.callout)
                .foregroundStyle(.secondary)
                .frame(width: 110, alignment: .trailing)
            Text(value)
                .font(.body)
            Spacer()
        }
        .padding(.vertical, 8)
    }
}
