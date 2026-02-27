import Foundation
import GRDB

/// An extracted medical result.
/// Maps to the `medical_results` table in vault.db.
/// Flat structure -- ResultValue fields (value, unit, reference_low/high, is_abnormal)
/// are stored as top-level columns in SQLite.
struct MedicalResult: Identifiable, Hashable, Sendable {
    let id: String
    let documentId: String
    let testName: String
    let value: String
    let unit: String?
    let referenceLow: String?
    let referenceHigh: String?
    let isAbnormal: Bool?
    let resultDate: String
    let category: ResultCategory
    let parserUsed: String
    let extractorVersion: String
    let confidence: Confidence
    let validationStatus: ValidationStatus
    let notes: String?
}

extension MedicalResult: FetchableRecord, Codable {
    enum CodingKeys: String, CodingKey {
        case id
        case documentId = "document_id"
        case testName = "test_name"
        case value
        case unit
        case referenceLow = "reference_low"
        case referenceHigh = "reference_high"
        case isAbnormal = "is_abnormal"
        case resultDate = "result_date"
        case category
        case parserUsed = "parser_used"
        case extractorVersion = "extractor_version"
        case confidence
        case validationStatus = "validation_status"
        case notes
    }
}

extension MedicalResult {
    /// Reference range formatted for display (e.g., "70 - 100").
    var referenceRange: String? {
        switch (referenceLow, referenceHigh) {
        case let (low?, high?):
            return "\(low) - \(high)"
        case let (low?, nil):
            return ">= \(low)"
        case let (nil, high?):
            return "<= \(high)"
        case (nil, nil):
            return nil
        }
    }

    /// The numeric value, if parseable.
    var numericValue: Double? {
        Double(value)
    }

    /// Formatted date for display (e.g., "Jan 15, 2025").
    var formattedDate: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        if let date = formatter.date(from: String(resultDate.prefix(10))) {
            let display = DateFormatter()
            display.dateStyle = .medium
            display.timeStyle = .none
            return display.string(from: date)
        }
        return String(resultDate.prefix(10))
    }
}
