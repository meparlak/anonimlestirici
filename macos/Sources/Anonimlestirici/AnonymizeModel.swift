import AppKit
import Foundation

/// Anonimleştir sekmesinin durumu: ana ekran → tarama → önizleme → sonuç.
@MainActor
final class AnonymizeModel: ObservableObject {
    enum Phase: Equatable {
        case home
        case working(String)
        case review
        case result
    }

    @Published var phase: Phase = .home
    @Published var progress: EngineProgress?
    @Published var candidates: [Candidate] = []
    @Published var documents: [String] = []
    @Published var warnings: [String] = []
    @Published var saved: SavedResult?
    @Published var alert: AlertItem?

    let engine: EngineClient
    let settings: AppSettings
    private var inputs: [URL] = []
    private var job: URL?
    private var started = Date()

    init(engine: EngineClient, settings: AppSettings) {
        self.engine = engine
        self.settings = settings
    }

    // MARK: Tarama

    func open(_ urls: [URL]) {
        var ok: [URL] = []
        var problems: [String] = []
        for u in urls {
            if let p = FileAccess.problem(with: u) {
                problems.append("\(u.lastPathComponent): \(p)")
            } else {
                ok.append(u)
            }
        }
        if !problems.isEmpty {
            alert = AlertItem(title: "Bazı dosyalar eklenmedi", message: problems.joined(separator: "\n\n"))
        }
        guard !ok.isEmpty else { return }
        Task { await analyze(ok) }
    }

    private func analyze(_ urls: [URL]) async {
        phase = .working(urls.count == 1 ? "\(urls[0].lastPathComponent) taranıyor" : "\(urls.count) dosya taranıyor")
        progress = nil
        started = Date()
        do {
            FileAccess.cleanup(job)
            let job = try FileAccess.newJobFolder()
            self.job = job
            inputs = urls
            let copies = try FileAccess.copyIn(urls, job: job)
            let _: Empty = try await engine.call("configure", ["settings": settings.engineSettings(engine.hello)])
            let res: AnalysisPayload = try await engine.call("analyze", ["paths": copies.map(\.path)]) { [weak self] p in
                self?.progress = p
            }
            apply(res)
            phase = .review
        } catch let e as EngineError where e.cancelled {
            phase = .home
        } catch {
            phase = .home
            alert = AlertItem(title: "Dosya taranamadı",
                              message: error.localizedDescription + "\n\nDosya parola korumalıysa parolayı kaldırıp yeniden deneyin.")
        }
    }

    private func apply(_ res: AnalysisPayload) {
        candidates = res.candidates
        documents = res.documents
        warnings = res.warnings
    }

    func cancel() { engine.cancel() }

    // MARK: Önizlemede düzenleme

    func setAccepted(_ ids: [Int], _ on: Bool) {
        Task {
            do {
                let res: AnalysisPayload = try await engine.call("set_accepted", ["ids": ids, "accepted": on])
                apply(res)
            } catch { show(error) }
        }
    }

    func setType(_ id: Int, _ type: String) {
        Task {
            do {
                let res: AnalysisPayload = try await engine.call("set_type", ["id": id, "type": type])
                apply(res)
            } catch { show(error) }
        }
    }

    func addManual(_ value: String, type: String) async -> (Int?, Int) {
        do {
            let res: AnalysisPayload = try await engine.call("add_manual", ["value": value, "type": type])
            apply(res)
            return (res.addedId, res.addedCount ?? 0)
        } catch {
            show(error)
            return (nil, 0)
        }
    }

    func exclude(_ c: Candidate) {
        if !settings.prefs.excludeTerms.contains(c.value) {
            settings.prefs.excludeTerms.append(c.value)
        }
        setAccepted([c.id], false)
    }

    // MARK: Kaydetme

    func save() {
        let firstFolder = inputs.first?.deletingLastPathComponent()
        var folder: URL?
        if !settings.prefs.askOutputFolder, let fixed = settings.outputFolder {
            folder = fixed
        } else {
            folder = FileAccess.chooseFolder(
                startingAt: settings.outputFolder ?? firstFolder,
                message: "Anonim dosya ve eşleştirme tablosu nereye kaydedilsin?")
        }
        guard let folder else { return }
        Task { await save(to: folder) }
    }

    private func save(to folder: URL) async {
        guard let job else { return }
        phase = .working("Kaydediliyor")
        progress = nil
        let t0 = Date()
        let scoped = folder.startAccessingSecurityScopedResource()
        defer { if scoped { folder.stopAccessingSecurityScopedResource() } }
        do {
            let out = job.appendingPathComponent("cikti")
            let res: SavePayload = try await engine.call("save", ["outDir": out.path]) { [weak self] p in
                self?.progress = p
            }
            var finals: [URL] = []
            for o in res.outputs {
                finals.append(try FileAccess.moveOut(URL(fileURLWithPath: o), to: folder))
            }
            let mapping = try FileAccess.moveOut(URL(fileURLWithPath: res.mapping), to: folder)
            saved = SavedResult(outputs: finals, mapping: mapping, replaced: res.replaced, distinct: res.distinct,
                                skipped: res.skipped, seconds: Date().timeIntervalSince(t0),
                                warnings: res.warnings)
            for f in finals {
                settings.addRecent(name: f.lastPathComponent, path: f.path, found: res.distinct)
            }
            phase = .result
        } catch {
            phase = .review
            alert = AlertItem(title: "Kaydedilemedi", message: error.localizedDescription)
        }
    }

    /// "Aynı kodlarla başka dosya ekle": motorun oturumu (kod havuzu) korunur.
    func continueSameSession() {
        candidates = []
        phase = .home
    }

    func newSession() {
        Task {
            let _: Empty? = try? await engine.call("new_session")
            candidates = []
            saved = nil
            FileAccess.cleanup(job)
            job = nil
            phase = .home
        }
    }

    private func show(_ error: Error) {
        alert = AlertItem(title: "İşlem tamamlanamadı", message: error.localizedDescription)
    }
}

struct AlertItem: Identifiable {
    let id = UUID()
    let title: String
    let message: String
}
