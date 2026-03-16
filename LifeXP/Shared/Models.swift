import Foundation

// MARK: - Steps

struct DailySteps: Codable, Identifiable {
    var id: String { date }
    let date: String        // "YYYY-MM-DD"
    let steps: Int

    var isGoalMet: Bool { steps >= 10_000 }
}

// MARK: - Weight

struct WeightEntry: Codable, Identifiable {
    var id: Double { timestamp }
    let timestamp: Double   // Unix timestamp
    let kg: Double

    var date: Date { Date(timeIntervalSince1970: timestamp) }

    var lbs: Double { kg * 2.20462 }

    var dateString: String {
        let f = DateFormatter()
        f.dateStyle = .short
        return f.string(from: date)
    }
}

// MARK: - Withings API Response Models

struct WithingsResponse<T: Codable>: Codable {
    let status: Int
    let body: T?
    let error: String?
}

struct WithingsActivityBody: Codable {
    let activities: [WithingsActivity]?
    let more: Bool?
    let offset: Int?
}

struct WithingsActivity: Codable {
    let date: String
    let steps: Int?
    let distance: Double?
    let calories: Double?
}

struct WithingsMeasureBody: Codable {
    let measuregrps: [WithingsMeasureGroup]?
    let more: Int?
    let offset: Int?
}

struct WithingsMeasureGroup: Codable {
    let grpid: Int
    let date: Int
    let category: Int
    let measures: [WithingsMeasure]
}

struct WithingsMeasure: Codable {
    let value: Int
    let type: Int
    let unit: Int

    /// Withings stores values as value * 10^unit
    var realValue: Double {
        Double(value) * pow(10.0, Double(unit))
    }
}

// MARK: - Token

struct WithingsTokens: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: Date
    let userId: String

    var isExpired: Bool { Date() >= expiresAt }
}

struct WithingsTokenResponse: Codable {
    let status: Int
    let body: WithingsTokenBody?
}

struct WithingsTokenBody: Codable {
    let userid: String?
    let access_token: String
    let refresh_token: String
    let expires_in: Int
}
