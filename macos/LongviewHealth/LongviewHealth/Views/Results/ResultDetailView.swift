import SwiftUI

struct ResultDetailView: View {
    let result: MedicalResult
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text(result.testName)
                    .font(.title3.weight(.semibold))
                Spacer()
                Button("Done") { dismiss() }
                    .keyboardShortcut(.cancelAction)
            }
            .padding(20)

            Divider()

            ScrollView {
                Grid(alignment: .leading, horizontalSpacing: 24, verticalSpacing: 12) {
                    detailRow("Value", content: {
                        HStack(spacing: 4) {
                            Text(result.value)
                                .font(.body.monospacedDigit().weight(.medium))
                            if let unit = result.unit {
                                Text(unit)
                                    .foregroundStyle(.secondary)
                            }
                            if result.isAbnormal == true {
                                Text("abnormal")
                                    .font(.caption.weight(.medium))
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.abnormalBackground)
                                    .foregroundStyle(.red)
                                    .clipShape(RoundedRectangle(cornerRadius: 4))
                            }
                        }
                    })

                    if let range = result.referenceRange {
                        detailRow("Reference Range", text: range)
                    }

                    detailRow("Date", text: result.formattedDate)

                    detailRow("Category", content: {
                        Label(result.category.displayName, systemImage: result.category.systemImage)
                    })

                    detailRow("Confidence", text: result.confidence.rawValue.capitalized)

                    detailRow("Validation", text: result.validationStatus.rawValue.capitalized)

                    detailRow("Extractor", text: "v\(result.extractorVersion) (\(result.parserUsed))")

                    detailRow("Document ID", text: String(result.documentId.prefix(12)) + "...")

                    if let notes = result.notes, !notes.isEmpty {
                        detailRow("Notes", text: notes)
                    }
                }
                .padding(20)
            }
        }
        .frame(minWidth: 400, idealWidth: 450, minHeight: 350)
    }

    private func detailRow(_ label: String, text: String) -> some View {
        detailRow(label) {
            Text(text)
        }
    }

    private func detailRow<Content: View>(_ label: String, @ViewBuilder content: () -> Content) -> some View {
        GridRow {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 110, alignment: .trailing)
            content()
        }
    }
}
