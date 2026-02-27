import Foundation

/// Categories of medical results, matching Python's ResultCategory.
enum ResultCategory: String, CaseIterable, Identifiable, Codable, Sendable {
    case lab
    case imaging
    case pathology
    case diagnostic
    case vital
    case other

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .lab: "Lab"
        case .imaging: "Imaging"
        case .pathology: "Pathology"
        case .diagnostic: "Diagnostic"
        case .vital: "Vital"
        case .other: "Other"
        }
    }

    var systemImage: String {
        switch self {
        case .lab: "flask"
        case .imaging: "camera.metering.unknown"
        case .pathology: "microscope"
        case .diagnostic: "waveform.path.ecg"
        case .vital: "heart"
        case .other: "doc.text"
        }
    }
}

/// Confidence level for extraction results.
enum Confidence: String, Codable, Sendable {
    case high
    case medium
    case low
}

/// Validation status for extraction results.
enum ValidationStatus: String, Codable, Sendable {
    case passed
    case flagged
    case rejected
    case pending
}

/// Sections available in the sidebar.
enum SidebarSection: String, CaseIterable, Identifiable, Sendable {
    case dashboard
    case results
    case trends
    case documents
    case review

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .dashboard: "Dashboard"
        case .results: "Results"
        case .trends: "Trends"
        case .documents: "Documents"
        case .review: "Review"
        }
    }

    var systemImage: String {
        switch self {
        case .dashboard: "square.grid.2x2"
        case .results: "list.bullet.clipboard"
        case .trends: "chart.xyaxis.line"
        case .documents: "doc.on.doc"
        case .review: "checkmark.circle"
        }
    }
}
