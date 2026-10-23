import Foundation

/// Kullanıcı tercihleri. Sandbox içinde UserDefaults uygulamanın kendi kabına yazılır.
struct Preferences: Codable, Equatable {
    var enabled: [String: Bool] = [:]
    var tcChecksum = true
    var nameAliases = true
    var nerEnabled = true
    var customTerms: [String] = []
    var excludeTerms: [String] = []
    var headers: [String: String]? = nil  // nil: motorun varsayılanları
    var codeFormat = "bracket"
    var outputSuffix = "_anonim"
    var cleanMetadata = true
    var askOutputFolder = true
    var llmEnabled = false
    var llmURL = "http://localhost:11434"
    var llmModel = "qwen2.5:3b"
    var llmAllowRemote = false
    var recent: [RecentItem] = []
}

struct RecentItem: Codable, Equatable, Identifiable {
    var id: String { path + when }
    let name: String
    let path: String
    let when: String
    let found: Int
}

@MainActor
final class AppSettings: ObservableObject {
    private static let key = "tercihler.v1"

    @Published var prefs: Preferences {
        didSet { if !ephemeral { save() } }
    }
    private var ephemeral = false

    /// Sabit çıktı klasörü (sandbox için güvenlik kapsamlı yer imi olarak saklanır).
    @Published private(set) var outputFolder: URL?

    /// Kaydetmeyen geçici ayarlar (ekran görüntüleri için).
    convenience init(ephemeral: Bool) {
        self.init()
        self.ephemeral = ephemeral
        prefs = Preferences()
    }

    init() {
        if let data = UserDefaults.standard.data(forKey: Self.key),
           let p = try? JSONDecoder().decode(Preferences.self, from: data) {
            prefs = p
        } else {
            prefs = Preferences()
        }
        outputFolder = Self.resolveBookmark()
    }

    private func save() {
        if let data = try? JSONEncoder().encode(prefs) {
            UserDefaults.standard.set(data, forKey: Self.key)
        }
    }

    func isEnabled(_ kind: EntityKind) -> Bool {
        prefs.enabled[kind.value] ?? kind.defaultEnabled
    }

    func setEnabled(_ kind: EntityKind, _ on: Bool) {
        prefs.enabled[kind.value] = on
    }

    func effectiveHeaders(_ hello: HelloPayload?) -> [String: String] {
        prefs.headers ?? hello?.defaults.headers ?? [:]
    }

    /// Motorun beklediği biçimde ayarlar (Python Settings alan adları).
    func engineSettings(_ hello: HelloPayload?) -> [String: Any] {
        var enabled: [String: Bool] = [:]
        for k in hello?.types ?? [] { enabled[k.value] = isEnabled(k) }
        var d: [String: Any] = [
            "enabled": enabled,
            "tc_checksum": prefs.tcChecksum,
            "name_aliases": prefs.nameAliases,
            "ner_enabled": prefs.nerEnabled,
            "custom_terms": prefs.customTerms,
            "exclude_terms": prefs.excludeTerms,
            "code_format": prefs.codeFormat,
            "output_suffix": prefs.outputSuffix.isEmpty ? "_anonim" : prefs.outputSuffix,
            "clean_metadata": prefs.cleanMetadata,
            "headers": effectiveHeaders(hello),
        ]
        #if STORE_BUILD
        d["llm"] = ["enabled": false]
        #else
        d["llm"] = ["enabled": prefs.llmEnabled, "url": prefs.llmURL, "model": prefs.llmModel,
                    "allow_remote": prefs.llmAllowRemote]
        #endif
        return d
    }

    func addRecent(name: String, path: String, found: Int) {
        let f = DateFormatter()
        f.locale = Locale(identifier: "tr_TR")
        f.dateFormat = "dd.MM.yyyy HH:mm"
        let item = RecentItem(name: name, path: path, when: f.string(from: Date()), found: found)
        prefs.recent = Array(([item] + prefs.recent).prefix(8))
    }

    // MARK: Sabit çıktı klasörü

    private static let bookmarkKey = "ciktiKlasoru.yerImi"

    func setOutputFolder(_ url: URL?) {
        guard let url else {
            UserDefaults.standard.removeObject(forKey: Self.bookmarkKey)
            outputFolder = nil
            return
        }
        if let data = try? url.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil,
                                            relativeTo: nil) {
            UserDefaults.standard.set(data, forKey: Self.bookmarkKey)
        }
        outputFolder = url
    }

    private static func resolveBookmark() -> URL? {
        guard let data = UserDefaults.standard.data(forKey: bookmarkKey) else { return nil }
        var stale = false
        return try? URL(resolvingBookmarkData: data, options: [.withSecurityScope], relativeTo: nil,
                        bookmarkDataIsStale: &stale)
    }
}
