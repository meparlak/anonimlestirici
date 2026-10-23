import Foundation

/// Motorun tanıdığı veri türü. Liste motorun `hello` cevabından gelir.
struct EntityKind: Codable, Hashable, Identifiable {
    let value: String
    let label: String
    let defaultEnabled: Bool
    var id: String { value }
}

struct Occurrence: Codable, Hashable {
    let file: String
    let location: String
    let context: String
    let start: Int  // UTF-16 konumu
    let end: Int
}

struct Candidate: Codable, Identifiable, Hashable {
    let id: Int
    let type: String
    let typeLabel: String
    let value: String
    let variants: [String]
    let code: String
    let count: Int
    let accepted: Bool
    let lowConfidence: Bool
    let confidence: Double
    let sources: [String]
    let files: [String]
    let occurrences: [Occurrence]
}

struct AnalysisPayload: Codable {
    let candidates: [Candidate]
    let documents: [String]
    let warnings: [String]
    var addedId: Int?
    var addedCount: Int?
}

struct SavePayload: Codable {
    let outputs: [String]
    let mapping: String
    let replaced: Int
    let distinct: Int
    let skipped: Int
    let warnings: [String]
}

struct HelloPayload: Codable {
    let version: String
    let ner: Bool
    let types: [EntityKind]
    let defaults: EngineDefaults
}

struct EngineDefaults: Codable {
    let headers: [String: String]
}

struct ReverseSpan: Codable, Hashable {
    let start: Int
    let end: Int
    let replacement: String
}

struct ReversePayload: Codable {
    let text: String
    let spans: [ReverseSpan]
    let replaced: Int
    let unknown: [String]
}

struct ReverseFilePayload: Codable {
    let output: String
    let replaced: Int
    let unknown: [String]
}

struct MappingInfo: Codable { let count: Int }
struct ModelsPayload: Codable { let models: [String] }
struct Empty: Codable {}

/// Sonuç ekranında gösterilen, kullanıcının klasörüne taşınmış dosyalar.
struct SavedResult {
    let outputs: [URL]
    let mapping: URL
    let replaced: Int
    let distinct: Int
    let skipped: Int
    let seconds: Double
    let warnings: [String]
}
