import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var api: WithingsAPI

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Connection status
                connectionCard

                // API credentials
                credentialsCard

                // Actions
                if api.isAuthenticated {
                    actionsCard
                }
            }
            .padding()
        }
    }

    private var connectionCard: some View {
        VStack(spacing: 12) {
            Image(systemName: api.isAuthenticated ? "checkmark.circle.fill" : "xmark.circle")
                .font(.system(size: 40))
                .foregroundStyle(api.isAuthenticated ? .green : .red)

            Text(api.isAuthenticated ? "Connected to Withings" : "Not Connected")
                .font(.headline)

            if let error = api.errorMessage {
                Text(error)
                    .font(.callout)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
            }

            if let lastRefresh = DataStore.shared.lastRefresh {
                Text("Last updated: \(lastRefresh.formatted(.relative(presentation: .named)))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var credentialsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Withings API Credentials")
                .font(.headline)

            Text("Register at developer.withings.com to get your Client ID and Secret. Set the callback URL to: lifexp://oauth/callback")
                .font(.caption)
                .foregroundStyle(.secondary)

            TextField("Client ID", text: $api.clientId)
                .textFieldStyle(.roundedBorder)

            SecureField("Client Secret", text: $api.clientSecret)
                .textFieldStyle(.roundedBorder)

            if !api.isAuthenticated {
                Button {
                    if let url = api.authorizationURL {
                        NSWorkspace.shared.open(url)
                    }
                } label: {
                    Label("Connect with Withings", systemImage: "link")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(api.clientId.isEmpty || api.clientSecret.isEmpty)
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var actionsCard: some View {
        VStack(spacing: 12) {
            Button {
                Task { await api.fetchAll() }
            } label: {
                Label("Refresh Data", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)

            Button(role: .destructive) {
                api.logout()
            } label: {
                Label("Disconnect", systemImage: "xmark.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
