#!/usr/bin/env swift

// Life XP — Apple HealthKit reader helper
// Compile: swiftc health_reader.swift -o health_reader
// Usage:   ./health_reader --metric weight --unit kg
//          ./health_reader --metric steps

import Foundation
import HealthKit

let healthStore = HKHealthStore()

// ── Parse arguments ──────────────────────────────────────────────────

var metric = "weight"
var unit = "kg"
var args = CommandLine.arguments.dropFirst()

while let arg = args.popFirst() {
    switch arg {
    case "--metric": if let val = args.popFirst() { metric = val }
    case "--unit":   if let val = args.popFirst() { unit = val }
    default: break
    }
}

// ── HealthKit availability check ─────────────────────────────────────

guard HKHealthStore.isHealthDataAvailable() else {
    fputs("error: HealthKit not available on this device\n", stderr)
    exit(1)
}

// ── Query latest sample ─────────────────────────────────────────────

let semaphore = DispatchSemaphore(value: 0)
var resultValue: String?

func queryLatest(sampleType: HKSampleType, unitType: HKUnit) {
    let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
    let query = HKSampleQuery(
        sampleType: sampleType,
        predicate: nil,
        limit: 1,
        sortDescriptors: [sort]
    ) { _, samples, error in
        if let error = error {
            fputs("error: \(error.localizedDescription)\n", stderr)
            semaphore.signal()
            return
        }
        if let sample = samples?.first as? HKQuantitySample {
            let value = sample.quantity.doubleValue(for: unitType)
            resultValue = String(format: "%.1f", value)
        } else {
            fputs("error: no data found for \(metric)\n", stderr)
        }
        semaphore.signal()
    }
    healthStore.execute(query)
}

// ── Request authorization and query ──────────────────────────────────

let (sampleType, hkUnit): (HKSampleType, HKUnit) = {
    switch metric {
    case "weight":
        let u: HKUnit = unit == "lbs" ? .pound() : .gramUnit(with: .kilo)
        return (HKQuantityType.quantityType(forIdentifier: .bodyMass)!, u)
    case "steps":
        return (HKQuantityType.quantityType(forIdentifier: .stepCount)!, .count())
    case "heart_rate":
        return (HKQuantityType.quantityType(forIdentifier: .heartRate)!, HKUnit.count().unitDivided(by: .minute()))
    case "active_energy":
        return (HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned)!, .kilocalorie())
    case "distance":
        let u: HKUnit = unit == "mi" ? .mile() : .meterUnit(with: .kilo)
        return (HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning)!, u)
    default:
        fputs("error: unsupported metric '\(metric)'\n", stderr)
        exit(1)
    }
}()

let typesToRead: Set<HKSampleType> = [sampleType]

healthStore.requestAuthorization(toShare: nil, read: typesToRead) { success, error in
    if !success {
        fputs("error: authorization denied — \(error?.localizedDescription ?? "unknown")\n", stderr)
        semaphore.signal()
        return
    }
    queryLatest(sampleType: sampleType, unitType: hkUnit)
}

semaphore.wait()

if let value = resultValue {
    print(value)
} else {
    exit(1)
}
