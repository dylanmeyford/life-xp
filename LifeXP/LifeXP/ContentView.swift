import SwiftUI

struct ContentView: View {
    @EnvironmentObject var api: WithingsAPI

    enum Tab: String, CaseIterable {
        case steps = "Steps"
        case weight = "Weight"
        case settings = "Settings"
    }

    @State private var selectedTab: Tab = .steps

    var body: some View {
        NavigationSplitView {
            List(Tab.allCases, id: \.self, selection: $selectedTab) { tab in
                Label(tab.rawValue, systemImage: icon(for: tab))
            }
            .navigationSplitViewColumnWidth(min: 140, ideal: 160)
        } detail: {
            switch selectedTab {
            case .steps:
                StepsView()
            case .weight:
                WeightView()
            case .settings:
                SettingsView()
            }
        }
        .navigationTitle("Life XP")
        .toolbar {
            ToolbarItem {
                if api.isLoading {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Button {
                        Task { await api.fetchAll() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(!api.isAuthenticated)
                    .help("Refresh data from Withings")
                }
            }
        }
        .task {
            if api.isAuthenticated {
                await api.fetchAll()
            }
        }
    }

    private func icon(for tab: Tab) -> String {
        switch tab {
        case .steps: return "figure.walk"
        case .weight: return "scalemass"
        case .settings: return "gear"
        }
    }
}
