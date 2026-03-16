import SwiftUI
import Charts

struct WeightView: View {
    @EnvironmentObject var api: WithingsAPI
    @AppStorage("weightUnit", store: UserDefaults(suiteName: DataStore.appGroup))
    private var useLbs = true

    private var entries: [WeightEntry] {
        DataStore.shared.weightEntries
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                latestCard
                if entries.count >= 2 {
                    weightChart
                }
                if !entries.isEmpty {
                    entryList
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

    private var latestCard: some View {
        let latest = entries.last
        let value = latest.map { useLbs ? $0.lbs : $0.kg }
        let unit = useLbs ? "lbs" : "kg"

        return VStack(spacing: 8) {
            Text("Latest Weight")
                .font(.headline)
                .foregroundStyle(.secondary)

            if let value {
                Text(String(format: "%.1f", value))
                    .font(.system(size: 48, weight: .bold, design: .rounded))

                Text(unit)
                    .font(.title3)
                    .foregroundStyle(.secondary)
            } else {
                Text("—")
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundStyle(.secondary)
            }

            if let latest {
                Text(latest.dateString)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            Picker("Unit", selection: $useLbs) {
                Text("lbs").tag(true)
                Text("kg").tag(false)
            }
            .pickerStyle(.segmented)
            .frame(width: 140)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var weightChart: some View {
        let data = entries.suffix(60)
        let values = data.map { useLbs ? $0.lbs : $0.kg }
        let minVal = (values.min() ?? 0) - 2
        let maxVal = (values.max() ?? 0) + 2
        let unit = useLbs ? "lbs" : "kg"

        return VStack(alignment: .leading) {
            Text("Weight Over Time")
                .font(.headline)

            Chart(Array(data)) { entry in
                let w = useLbs ? entry.lbs : entry.kg
                LineMark(
                    x: .value("Date", entry.date),
                    y: .value(unit, w)
                )
                .interpolationMethod(.catmullRom)
                .foregroundStyle(.blue)

                PointMark(
                    x: .value("Date", entry.date),
                    y: .value(unit, w)
                )
                .symbolSize(30)
                .foregroundStyle(.blue)
            }
            .chartYScale(domain: minVal...maxVal)
            .frame(height: 250)
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var entryList: some View {
        let unit = useLbs ? "lbs" : "kg"

        return VStack(alignment: .leading, spacing: 8) {
            Text("Weigh-ins")
                .font(.headline)

            ForEach(entries.reversed().prefix(30)) { entry in
                HStack {
                    Image(systemName: "scalemass")
                        .foregroundStyle(.blue)

                    Text(entry.dateString)
                        .font(.body.monospacedDigit())

                    Spacer()

                    Text(String(format: "%.1f %@", useLbs ? entry.lbs : entry.kg, unit))
                        .foregroundStyle(.secondary)
                        .font(.body.monospacedDigit())
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
