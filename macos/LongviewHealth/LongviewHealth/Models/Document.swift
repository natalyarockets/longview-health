import Foundation
import GRDB

/// A source document indexed in the vault.
/// Maps to the `documents` table in vault.db.
struct Document: Identifiable, Hashable, Sendable {
    let id: String
    let vaultName: String
    let filename: String
    let filePath: String
    let documentType: String
    let contentHash: String
    let ingestedAt: String
    let pageCount: Int?
}

extension Document: FetchableRecord, Codable {
    /// Column mapping: SQLite snake_case -> Swift camelCase.
    enum CodingKeys: String, CodingKey {
        case id
        case vaultName = "vault_name"
        case filename
        case filePath = "file_path"
        case documentType = "document_type"
        case contentHash = "content_hash"
        case ingestedAt = "ingested_at"
        case pageCount = "page_count"
    }
}
