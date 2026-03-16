import SwiftUI
import WidgetKit
import Charts

struct WeightEntry: TimelineEntry {
    let date: Date
    let entries: [WeightDataPoint]
    let latest: Double?
    let useLbs: Bool
}

struct WeightDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let value: Double
}

struct WeightProvider: TimelineProvider {
    func placeholder(in context: Context) -> WeightEntry {
        let now = Date()
        let samples = (0..<14).map { i in
            WeightDataPoint(
                date: Calendar.current.date(byAdding: .day, value: -13 + i, to: now)!,
                value: 175.0 + Double.random(in: -2...2)
            )
        }
        return WeightEntry(date: now, entries: samples, latest: 174.5, useLbs: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (WeightEntry) -> Void) {
        completion(currentEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<WeightEntry>) -> Void) {
        let entry = currentEntry()
        let next = Calendar.current.date(byAdding: .hour, value: 1, to: .now)!
        completion(Timeline(entries: [entry], policy: .after(next)))
    }

    private func currentEntry() -> WeightEntry {
        let store = DataStore.shared
        let useLbs = UserDefaults(suiteName: DataStore.appGroup)?.bool(forKey: "weightUnit") ?? true
        let raw = store.weightEntries.suffix(30)

        let points = raw.map { entry in
            WeightDataPoint(
                date: entry.date,
                value: useLbs ? entry.lbs : entry.kg
            )
        }

        let latest = points.last?.value

        return WeightEntry(date: .now, entries: points, latest: latest, useLbs: useLbs)
    }
}

struct WeightWidgetView: View {
    var entry: WeightEntry
    @Environment(\.widgetFamily) var family

    private var unit: String { entry.useLbs ? "lbs" : "kg" }

    var body: some View {
        switch family {
        case .systemSmall:
            smallView
        case .systemMedium:
            mediumView
        default:
            smallView
        }
    }

    private var smallView: some View {
        VStack(spacing: 6) {
            Image(systemName: "scalemass")
                .font(.title3)
                .foregroundStyle(.blue)

            if let latest = entry.latest {
                Text(String(format: "%.1f", latest))
                    .font(.system(.title, design: .rounded, weight: .bold))
                    .minimumScaleFactor(0.6)

                Text(unit)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("—")
                    .font(.title)
                    .foregroundStyle(.secondary)
            }

            if entry.entries.count >= 2 {
                miniChart
                    .frame(height: 36)
            }
        }
        .containerBackground(.clear, for: .widget)
    }

    private var mediumView: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Label("Weight", systemImage: "scalemass")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                if let latest = entry.latest {
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.1f", latest))
                            .font(.system(.title, design: .rounded, weight: .bold))

                        Text(unit)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if let trend = trendText {
                    Text(trend)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 90)

            if entry.entries.count >= 2 {
                lineChart
            }
        }
        .containerBackground(.clear, for: .widget)
    }

    private var miniChart: some View {
        Chart(entry.entries) { point in
            LineMark(
                x: .value("Date", point.date),
                y: .value(unit, point.value)
            )
            .interpolationMethod(.catmullRom)
            .foregroundStyle(.blue)
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
    }

    private var lineChart: some View {
        let values = entry.entries.map(\.value)
        let lo = (values.min() ?? 0) - 1
        let hi = (values.max() ?? 0) + 1

        return Chart(entry.entries) { point in
            LineMark(
                x: .value("Date", point.date),
                y: .value(unit, point.value)
            )
            .interpolationMethod(.catmullRom)
            .foregroundStyle(.blue)

            PointMark(
                x: .value("Date", point.date),
                y: .value(unit, point.value)
            )
            .symbolSize(15)
            .foregroundStyle(.blue)
        }
        .chartYScale(domain: lo...hi)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                    .font(.system(size: 8))
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { _ in
                AxisGridLine()
                AxisValueLabel()
                    .font(.system(size: 8))
            }
        }
    }

    private var trendText: String? {
        guard entry.entries.count >= 2 else { return nil }
        let first = entry.entries.first!.value
        let last = entry.entries.last!.value
        let diff = last - first
        let sign = diff >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", diff)) \(unit) over \(entry.entries.count) weigh-ins"
    }
}

struct WeightWidget: Widget {
    let kind = "WeightWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: WeightProvider()) { entry in
            WeightWidgetView(entry: entry)
        }
        .configurationDisplayName("Weight Tracker")
        .description("See your weight trend as a line graph.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
