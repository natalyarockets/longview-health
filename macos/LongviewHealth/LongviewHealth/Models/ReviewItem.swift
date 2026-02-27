import Foundation
import GRDB

/// An item in the review queue awaiting manual review.
/// Maps to the `review_queue` table in vault.db.
struct ReviewItem: Identifiable, Hashable, Sendable {
    let id: String
    let resultId: String
    let documentId: String
    let testName: String
    let reason: String
    let createdAt: String
    let resolved: Bool
    let resolvedAt: String?
}

extension ReviewItem: FetchableRecord, Codable {
    enum CodingKeys: String, CodingKey {
        case id
        case resultId = "result_id"
        case documentId = "document_id"
        case testName = "test_name"
        case reason
        case createdAt = "created_at"
        case resolved
        case resolvedAt = "resolved_at"
    }
}

extension ReviewItem {
    /// Formatted creation date for display.
    var formattedDate: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        if let date = formatter.date(from: String(createdAt.prefix(10))) {
            let display = DateFormatter()
            display.dateStyle = .medium
            display.timeStyle = .none
            return display.string(from: date)
        }
        return String(createdAt.prefix(10))
    }
}
