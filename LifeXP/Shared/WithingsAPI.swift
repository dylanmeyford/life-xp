import Foundation

/// Withings API client handling OAuth2 and data fetching.
final class WithingsAPI: ObservableObject {
    static let shared = WithingsAPI()

    // The user registers at https://developer.withings.com and fills these in.
    // Stored in the app's configuration.
    @Published var clientId: String {
        didSet { UserDefaults(suiteName: DataStore.appGroup)?.set(clientId, forKey: "withings_client_id") }
    }
    @Published var clientSecret: String {
        didSet { UserDefaults(suiteName: DataStore.appGroup)?.set(clientSecret, forKey: "withings_client_secret") }
    }

    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    static let callbackURL = "lifexp://oauth/callback"
    static let authBaseURL = "https://account.withings.com/oauth2_user/authorize2"
    static let tokenURL = "https://wbsapi.withings.net/v2/oauth2"
    static let measureURL = "https://wbsapi.withings.net/measure"
    static let activityURL = "https://wbsapi.withings.net/v2/measure"

    private let store = DataStore.shared

    private init() {
        let defaults = UserDefaults(suiteName: DataStore.appGroup)
        clientId = defaults?.string(forKey: "withings_client_id") ?? ""
        clientSecret = defaults?.string(forKey: "withings_client_secret") ?? ""
        isAuthenticated = store.tokens != nil
    }

    // MARK: - OAuth

    var authorizationURL: URL? {
        guard !clientId.isEmpty else { return nil }
        // Use the login endpoint with b=authorize2 so existing users see
        // the sign-in form instead of registration.
        var components = URLComponents(string: "https://account.withings.com/oauth2_user/login")!
        components.queryItems = [
            URLQueryItem(name: "b", value: "authorize2"),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "redirect_uri", value: Self.callbackURL),
            URLQueryItem(name: "scope", value: "user.metrics,user.activity"),
            URLQueryItem(name: "state", value: UUID().uuidString),
        ]
        return components.url
    }

    func exchangeCode(_ code: String) async throws {
        let params: [String: String] = [
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": clientId,
            "client_secret": clientSecret,
            "code": code,
            "redirect_uri": Self.callbackURL,
        ]

        let tokenResponse: WithingsTokenResponse = try await post(url: Self.tokenURL, params: params)

        guard tokenResponse.status == 0, let body = tokenResponse.body else {
            throw APIError.authFailed("Token exchange failed (status: \(tokenResponse.status))")
        }

        store.tokens = WithingsTokens(
            accessToken: body.access_token,
            refreshToken: body.refresh_token,
            expiresAt: Date().addingTimeInterval(TimeInterval(body.expires_in)),
            userId: body.userid ?? ""
        )

        await MainActor.run { isAuthenticated = true }
    }

    func refreshTokenIfNeeded() async throws {
        guard let tokens = store.tokens else { throw APIError.notAuthenticated }
        guard tokens.isExpired else { return }

        let params: [String: String] = [
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": clientId,
            "client_secret": clientSecret,
            "refresh_token": tokens.refreshToken,
        ]

        let tokenResponse: WithingsTokenResponse = try await post(url: Self.tokenURL, params: params)

        guard tokenResponse.status == 0, let body = tokenResponse.body else {
            store.tokens = nil
            await MainActor.run { isAuthenticated = false }
            throw APIError.authFailed("Refresh failed")
        }

        store.tokens = WithingsTokens(
            accessToken: body.access_token,
            refreshToken: body.refresh_token,
            expiresAt: Date().addingTimeInterval(TimeInterval(body.expires_in)),
            userId: body.userid ?? tokens.userId
        )
    }

    func logout() {
        store.tokens = nil
        isAuthenticated = false
    }

    // MARK: - Data Fetching

    func fetchAll() async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            try await refreshTokenIfNeeded()
            async let s: () = fetchSteps()
            async let w: () = fetchWeight()
            try await s
            try await w
            store.lastRefresh = Date()
        } catch {
            await MainActor.run { errorMessage = error.localizedDescription }
        }

        await MainActor.run { isLoading = false }
    }

    func fetchSteps() async throws {
        guard let token = store.tokens?.accessToken else { throw APIError.notAuthenticated }

        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -30, to: endDate)!

        let params: [String: String] = [
            "action": "getactivity",
            "startdateymd": DataStore.dateString(for: startDate),
            "enddateymd": DataStore.dateString(for: endDate),
        ]

        let response: WithingsResponse<WithingsActivityBody> = try await authenticatedPost(
            url: Self.activityURL, params: params, token: token
        )

        guard response.status == 0, let body = response.body, let activities = body.activities else {
            return
        }

        let steps = activities.compactMap { activity -> DailySteps? in
            guard let s = activity.steps else { return nil }
            return DailySteps(date: activity.date, steps: s)
        }

        store.dailySteps = steps.sorted { $0.date > $1.date }
    }

    func fetchWeight() async throws {
        guard let token = store.tokens?.accessToken else { throw APIError.notAuthenticated }

        let endDate = Date()
        let startDate = Calendar.current.date(byAdding: .month, value: -6, to: endDate)!

        let params: [String: String] = [
            "action": "getmeas",
            "meastype": "1",       // 1 = weight
            "category": "1",       // 1 = real measures only
            "startdate": "\(Int(startDate.timeIntervalSince1970))",
            "enddate": "\(Int(endDate.timeIntervalSince1970))",
        ]

        let response: WithingsResponse<WithingsMeasureBody> = try await authenticatedPost(
            url: Self.measureURL, params: params, token: token
        )

        guard response.status == 0, let body = response.body, let groups = body.measuregrps else {
            return
        }

        let entries = groups.compactMap { group -> WeightEntry? in
            guard let weightMeasure = group.measures.first(where: { $0.type == 1 }) else { return nil }
            return WeightEntry(timestamp: Double(group.date), kg: weightMeasure.realValue)
        }

        store.weightEntries = entries.sorted { $0.timestamp < $1.timestamp }
    }

    // MARK: - Networking

    private func authenticatedPost<T: Codable>(url: String, params: [String: String], token: String) async throws -> T {
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.httpBody = params.urlEncoded.data(using: .utf8)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post<T: Codable>(url: String, params: [String: String]) async throws -> T {
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.httpBody = params.urlEncoded.data(using: .utf8)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }

    // MARK: - Errors

    enum APIError: LocalizedError {
        case notAuthenticated
        case authFailed(String)

        var errorDescription: String? {
            switch self {
            case .notAuthenticated: return "Not authenticated with Withings"
            case .authFailed(let msg): return msg
            }
        }
    }
}

extension Dictionary where Key == String, Value == String {
    var urlEncoded: String {
        map { key, value in
            let k = key.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? key
            let v = value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? value
            return "\(k)=\(v)"
        }.joined(separator: "&")
    }
}
