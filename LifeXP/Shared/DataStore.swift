import Foundation

/// Shared data store using App Group UserDefaults so the widget can read it.
final class DataStore {
    static let shared = DataStore()

    private let defaults: UserDefaults
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    static let appGroup = "group.com.lifexp.shared"

    private init() {
        defaults = UserDefaults(suiteName: DataStore.appGroup) ?? .standard
    }

    // MARK: - Tokens

    var tokens: WithingsTokens? {
        get { load("withings_tokens") }
        set { save(newValue, key: "withings_tokens") }
    }

    // MARK: - Steps

    var dailySteps: [DailySteps] {
        get { load("daily_steps") ?? [] }
        set { save(newValue, key: "daily_steps") }
    }

    var todaySteps: DailySteps? {
        let today = Self.dateString(for: Date())
        return dailySteps.first { $0.date == today }
    }

    // MARK: - Weight

    var weightEntries: [WeightEntry] {
        get { load("weight_entries") ?? [] }
        set { save(newValue, key: "weight_entries") }
    }

    // MARK: - Last Refresh

    var lastRefresh: Date? {
        get { defaults.object(forKey: "last_refresh") as? Date }
        set { defaults.set(newValue, forKey: "last_refresh") }
    }

    // MARK: - Helpers

    static func dateString(for date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    private func save<T: Codable>(_ value: T?, key: String) {
        guard let value else {
            defaults.removeObject(forKey: key)
            return
        }
        if let data = try? encoder.encode(value) {
            defaults.set(data, forKey: key)
        }
    }

    private func load<T: Codable>(_ key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? decoder.decode(T.self, from: data)
    }
}
