import SwiftUI
import WidgetKit

struct StepsEntry: TimelineEntry {
    let date: Date
    let steps: Int
    let goalMet: Bool
}

struct StepsProvider: TimelineProvider {
    func placeholder(in context: Context) -> StepsEntry {
        StepsEntry(date: .now, steps: 7_500, goalMet: false)
    }

    func getSnapshot(in context: Context, completion: @escaping (StepsEntry) -> Void) {
        let entry = currentEntry()
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<StepsEntry>) -> Void) {
        let entry = currentEntry()
        // Refresh every 30 minutes
        let next = Calendar.current.date(byAdding: .minute, value: 30, to: .now)!
        completion(Timeline(entries: [entry], policy: .after(next)))
    }

    private func currentEntry() -> StepsEntry {
        let store = DataStore.shared
        let today = store.todaySteps
        let steps = today?.steps ?? 0
        return StepsEntry(date: .now, steps: steps, goalMet: steps >= 10_000)
    }
}

struct StepsWidgetView: View {
    var entry: StepsEntry
    @Environment(\.widgetFamily) var family

    var progress: Double { min(Double(entry.steps) / 10_000.0, 1.0) }

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
            Image(systemName: "figure.walk")
                .font(.title2)
                .foregroundStyle(entry.goalMet ? .green : .blue)

            Text("\(entry.steps.formatted())")
                .font(.system(.title, design: .rounded, weight: .bold))
                .foregroundStyle(entry.goalMet ? .green : .primary)
                .minimumScaleFactor(0.6)

            Text("steps")
                .font(.caption)
                .foregroundStyle(.secondary)

            // Progress ring
            ZStack {
                Circle()
                    .stroke(.quaternary, lineWidth: 4)
                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(
                        entry.goalMet ? Color.green : Color.blue,
                        style: StrokeStyle(lineWidth: 4, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
            }
            .frame(width: 36, height: 36)
            .overlay {
                if entry.goalMet {
                    Image(systemName: "checkmark")
                        .font(.caption.bold())
                        .foregroundStyle(.green)
                } else {
                    Text("\(Int(progress * 100))%")
                        .font(.system(size: 9, weight: .medium, design: .rounded))
                }
            }
        }
        .containerBackground(for: .widget) {
            entry.goalMet
                ? Color.green.opacity(0.08)
                : Color.clear
        }
    }

    private var mediumView: some View {
        HStack(spacing: 16) {
            // Left: main number
            VStack(spacing: 4) {
                Image(systemName: "figure.walk")
                    .font(.title2)
                    .foregroundStyle(entry.goalMet ? .green : .blue)

                Text("\(entry.steps.formatted())")
                    .font(.system(.largeTitle, design: .rounded, weight: .bold))
                    .foregroundStyle(entry.goalMet ? .green : .primary)

                Text("of 10,000 steps")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            // Right: progress ring
            ZStack {
                Circle()
                    .stroke(.quaternary, lineWidth: 8)
                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(
                        entry.goalMet ? Color.green : Color.blue,
                        style: StrokeStyle(lineWidth: 8, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
            }
            .frame(width: 70, height: 70)
            .overlay {
                VStack(spacing: 0) {
                    if entry.goalMet {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.green)
                    } else {
                        Text("\(Int(progress * 100))%")
                            .font(.system(.title3, design: .rounded, weight: .semibold))
                    }
                }
            }
        }
        .containerBackground(for: .widget) {
            entry.goalMet
                ? Color.green.opacity(0.08)
                : Color.clear
        }
    }
}

struct StepsWidget: Widget {
    let kind = "StepsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: StepsProvider()) { entry in
            StepsWidgetView(entry: entry)
        }
        .configurationDisplayName("Daily Steps")
        .description("Track your daily step count toward your 10,000 step goal.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
