import SwiftUI

@main
struct LifeXPApp: App {
    @StateObject private var api = WithingsAPI.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(api)
                .onOpenURL { url in
                    handleCallback(url)
                }
        }
        .defaultSize(width: 600, height: 500)
    }

    private func handleCallback(_ url: URL) {
        guard url.scheme == "lifexp",
              url.host == "oauth",
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let code = components.queryItems?.first(where: { $0.name == "code" })?.value
        else { return }

        Task {
            try? await api.exchangeCode(code)
            await api.fetchAll()
        }
    }
}
