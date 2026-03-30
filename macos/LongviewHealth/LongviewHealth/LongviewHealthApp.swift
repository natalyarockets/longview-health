import SwiftUI

@main
struct LongviewHealthApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .tint(Theme.accent)
        }
        .defaultSize(width: 1000, height: 680)
    }
}
