import SwiftUI

/// Longview Health design system.
/// Calming, healthful palette with soft teal accents and warm neutrals.
enum Theme {

    // MARK: - Brand Colors

    /// Primary teal — conveys health, calm, trust.
    static let accent = Color(hue: 0.47, saturation: 0.45, brightness: 0.72)

    /// Lighter tint for backgrounds and subtle fills.
    static let accentTint = Color(hue: 0.47, saturation: 0.12, brightness: 0.96)

    /// Warm surface for cards — not pure white, slightly warm.
    static let cardBackground = Color(nsColor: .controlBackgroundColor)

    /// Soft green for normal/healthy states.
    static let positive = Color(hue: 0.38, saturation: 0.40, brightness: 0.68)
    static let positiveTint = Color(hue: 0.38, saturation: 0.10, brightness: 0.96)

    /// Warm amber for abnormal/attention states — less alarming than red.
    static let attention = Color(hue: 0.06, saturation: 0.55, brightness: 0.90)
    static let attentionTint = Color(hue: 0.06, saturation: 0.12, brightness: 0.97)

    /// Soft red for reject/critical (used sparingly).
    static let critical = Color(hue: 0.0, saturation: 0.50, brightness: 0.82)

    /// Subtle border for cards.
    static let cardBorder = Color.primary.opacity(0.06)

    /// Chart reference range band.
    static let referenceRangeFill = Color(hue: 0.38, saturation: 0.15, brightness: 0.92)

    // MARK: - Typography Helpers

    static let largeTitleFont = Font.system(.title2, design: .rounded, weight: .semibold)
    static let sectionHeaderFont = Font.system(.headline, design: .rounded, weight: .medium)
    static let metricFont = Font.system(.largeTitle, design: .rounded, weight: .bold)
    static let captionFont = Font.system(.caption, design: .default)
}

// MARK: - Reusable Card Modifier

struct CardStyle: ViewModifier {
    var padding: CGFloat = 16

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Theme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(Theme.cardBorder, lineWidth: 1)
            )
    }
}

extension View {
    func cardStyle(padding: CGFloat = 16) -> some View {
        modifier(CardStyle(padding: padding))
    }
}

// MARK: - Status Badge

struct StatusBadge: View {
    let text: String
    let color: Color
    let tint: Color

    init(_ text: String, color: Color = Theme.attention, tint: Color = Theme.attentionTint) {
        self.text = text
        self.color = color
        self.tint = tint
    }

    var body: some View {
        Text(text)
            .font(.caption.weight(.medium))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(tint)
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
