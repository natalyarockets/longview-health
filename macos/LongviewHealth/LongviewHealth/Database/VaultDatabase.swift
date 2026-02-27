import Foundation
import GRDB

/// Read-only database connection to a vault's SQLite database.
/// Uses GRDB DatabasePool for concurrent reads while the Python CLI writes.
/// WAL mode is already enabled by the Python side (database.py:18).
final class VaultDatabase: Sendable {

    let dbPool: DatabasePool

    init(path: URL) throws {
        var config = Configuration()
        // Not using readonly flag -- WAL mode requires access to -wal/-shm files
        // which readonly connections can't create when they don't exist.
        // Read-only contract is enforced at the application layer: all mutations
        // go through CLIRunner -> Python CLI. This class never issues writes.
        config.busyMode = .timeout(5)
        dbPool = try DatabasePool(path: path.path, configuration: config)
    }

    // MARK: - Documents

    func fetchDocuments() throws -> [Document] {
        try dbPool.read { db in
            try Document.fetchAll(db, sql: """
                SELECT * FROM documents ORDER BY filename ASC
                """)
        }
    }

    func documentCount() throws -> Int {
        try dbPool.read { db in
            try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM documents") ?? 0
        }
    }

    func searchDocuments(query: String) throws -> [Document] {
        try dbPool.read { db in
            try Document.fetchAll(db, sql: """
                SELECT d.* FROM documents d
                JOIN documents_fts fts ON fts.document_id = d.id
                WHERE documents_fts MATCH ?
                ORDER BY rank
                """, arguments: [query])
        }
    }

    // MARK: - Medical Results

    func fetchResults(category: ResultCategory? = nil, testName: String? = nil) throws -> [MedicalResult] {
        try dbPool.read { db in
            var sql = "SELECT * FROM medical_results WHERE 1=1"
            var arguments: [any DatabaseValueConvertible] = []

            if let category {
                sql += " AND category = ?"
                arguments.append(category.rawValue)
            }
            if let testName {
                sql += " AND test_name = ?"
                arguments.append(testName)
            }

            sql += " ORDER BY result_date DESC"

            return try MedicalResult.fetchAll(db, sql: sql, arguments: StatementArguments(arguments))
        }
    }

    func fetchResultsForTest(_ testName: String) throws -> [MedicalResult] {
        try dbPool.read { db in
            try MedicalResult.fetchAll(db, sql: """
                SELECT * FROM medical_results
                WHERE test_name = ?
                ORDER BY result_date ASC
                """, arguments: [testName])
        }
    }

    func fetchDistinctTests() throws -> [String] {
        try dbPool.read { db in
            try String.fetchAll(db, sql: """
                SELECT DISTINCT test_name FROM medical_results
                ORDER BY test_name ASC
                """)
        }
    }

    func resultCountsByCategory() throws -> [ResultCategory: Int] {
        try dbPool.read { db in
            let rows = try Row.fetchAll(db, sql: """
                SELECT category, COUNT(*) as count FROM medical_results
                GROUP BY category
                """)
            var counts: [ResultCategory: Int] = [:]
            for row in rows {
                if let cat = ResultCategory(rawValue: row["category"]) {
                    counts[cat] = row["count"]
                }
            }
            return counts
        }
    }

    func resultCount() throws -> Int {
        try dbPool.read { db in
            try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM medical_results") ?? 0
        }
    }

    func dateRange() throws -> (earliest: String, latest: String)? {
        try dbPool.read { db in
            let row = try Row.fetchOne(db, sql: """
                SELECT MIN(result_date) as earliest, MAX(result_date) as latest
                FROM medical_results
                """)
            guard let row,
                  let earliest: String = row["earliest"],
                  let latest: String = row["latest"] else {
                return nil
            }
            return (earliest, latest)
        }
    }

    /// Distinct test names grouped by category.
    func testsByCategory() throws -> [(category: ResultCategory, tests: [String])] {
        try dbPool.read { db in
            let rows = try Row.fetchAll(db, sql: """
                SELECT DISTINCT category, test_name FROM medical_results
                ORDER BY category ASC, test_name ASC
                """)

            var grouped: [ResultCategory: [String]] = [:]
            for row in rows {
                if let cat = ResultCategory(rawValue: row["category"]) {
                    grouped[cat, default: []].append(row["test_name"])
                }
            }

            return ResultCategory.allCases.compactMap { cat in
                guard let tests = grouped[cat], !tests.isEmpty else { return nil }
                return (category: cat, tests: tests)
            }
        }
    }

    // MARK: - Review Queue

    func fetchPendingReviews() throws -> [ReviewItem] {
        try dbPool.read { db in
            try ReviewItem.fetchAll(db, sql: """
                SELECT * FROM review_queue
                WHERE resolved = 0
                ORDER BY created_at DESC
                """)
        }
    }

    func pendingReviewCount() throws -> Int {
        try dbPool.read { db in
            try Int.fetchOne(db, sql: """
                SELECT COUNT(*) FROM review_queue WHERE resolved = 0
                """) ?? 0
        }
    }

    // MARK: - Live Observation

    /// Observe changes to the medical_results table.
    func observeResults() -> ValueObservation<ValueReducers.Fetch<[MedicalResult]>> {
        ValueObservation.tracking { db in
            try MedicalResult.fetchAll(db, sql: """
                SELECT * FROM medical_results ORDER BY result_date DESC
                """)
        }
    }

    /// Observe the pending review count.
    func observePendingReviewCount() -> ValueObservation<ValueReducers.Fetch<Int>> {
        ValueObservation.tracking { db in
            try Int.fetchOne(db, sql: """
                SELECT COUNT(*) FROM review_queue WHERE resolved = 0
                """) ?? 0
        }
    }

    /// Observe the document count.
    func observeDocumentCount() -> ValueObservation<ValueReducers.Fetch<Int>> {
        ValueObservation.tracking { db in
            try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM documents") ?? 0
        }
    }
}
