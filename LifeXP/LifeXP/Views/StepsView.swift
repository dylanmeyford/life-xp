import SwiftUI
import Charts

struct StepsView: View {
    @EnvironmentObject var api: WithingsAPI

    private var steps: [DailySteps] {
        DataStore.shared.dailySteps
    }

    private var today: DailySteps? {
        DataStore.shared.todaySteps
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Today's card
                todayCard

                // Chart of last 30 days
                if !steps.isEmpty {
                    stepsChart
                }

                // Recent days list
                if !steps.isEmpty {
                    recentList
                }
            }
            .padding()
        }
        .overlay {
            if !api.isAuthenticated {
                ContentUnavailableView(
                    "Connect Withings",
                    systemImage: "link.badge.plus",
                    description: Text("Go to Settings to connect your Withings account.")
                )
            }
        }
    }

    private var todayCard: some View {
        let count = today?.steps ?? 0
        let goalMet = count >= 10_000
        let progress = min(Double(count) / 10_000.0, 1.0)

        return VStack(spacing: 12) {
            Text("Today")
                .font(.headline)
                .foregroundStyle(.secondary)

            Text("\(count.formatted())")
                .font(.system(size: 48, weight: .bold, design: .rounded))
                .foregroundStyle(goalMet ? .green : .primary)

            Text("steps")
                .font(.title3)
                .foregroundStyle(.secondary)

            ProgressView(value: progress)
                .tint(goalMet ? .green : .blue)
                .scaleEffect(y: 2)
                .padding(.horizontal, 40)

            Text(goalMet ? "Goal reached!" : "\((10_000 - count).formatted()) to go")
                .font(.callout)
                .foregroundStyle(goalMet ? .green : .secondary)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var stepsChart: some View {
        let sorted = steps.sorted { $0.date < $1.date }.suffix(14)

        return VStack(alignment: .leading) {
            Text("Last 14 Days")
                .font(.headline)

            Chart(Array(sorted)) { day in
                BarMark(
                    x: .value("Date", day.date.suffix(5)),
                    y: .value("Steps", day.steps)
                )
                .foregroundStyle(day.isGoalMet ? .green : .blue)

                RuleMark(y: .value("Goal", 10_000))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5]))
                    .foregroundStyle(.orange.opacity(0.7))
            }
            .frame(height: 200)
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var recentList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("History")
                .font(.headline)

            ForEach(steps.prefix(30)) { day in
                HStack {
                    Circle()
                        .fill(day.isGoalMet ? .green : .red.opacity(0.4))
                        .frame(width: 10, height: 10)

                    Text(day.date)
                        .font(.body.monospacedDigit())

                    Spacer()

                    Text("\(day.steps.formatted()) steps")
                        .foregroundStyle(.secondary)
                        .font(.body.monospacedDigit())
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
