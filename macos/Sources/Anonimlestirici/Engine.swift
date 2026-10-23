import Foundation

struct EngineError: LocalizedError {
    let message: String
    var cancelled = false
    var errorDescription: String? { message }
}

struct EngineProgress {
    let done: Int
    let total: Int
    let message: String
}

/// Paketin içindeki Python motorunu yardımcı süreç olarak çalıştırır ve onunla
/// satır satır JSON ile konuşur (bkz. anonimlestirici/server.py).
@MainActor
final class EngineClient: ObservableObject {
    @Published private(set) var hello: HelloPayload?
    @Published private(set) var startError: String?

    private var process: Process?
    private var stdin: FileHandle?
    private var buffer = Data()
    private var nextId = 1
    private var pending: [Int: CheckedContinuation<Data, Error>] = [:]
    private var progressHandlers: [Int: (EngineProgress) -> Void] = [:]

    /// Motorun çalıştırılabilir dosyası ve argümanları.
    /// Paketlenmiş uygulamada Contents/Helpers içindeki yardımcı uygulama kullanılır.
    /// Geliştirirken ANONIM_ENGINE ortam değişkeniyle bir Python yorumlayıcısı verilebilir.
    static func engineCommand() -> (URL, [String])? {
        let env = ProcessInfo.processInfo.environment
        if let py = env["ANONIM_ENGINE"] {
            return (URL(fileURLWithPath: py), ["-m", "anonimlestirici", "serve"])
        }
        let helper = Bundle.main.bundleURL
            .appendingPathComponent("Contents/Helpers/AnonimEngine.app/Contents/MacOS/anonim-engine")
        if FileManager.default.isExecutableFile(atPath: helper.path) {
            return (helper, ["serve"])
        }
        return nil
    }

    func start() {
        guard process == nil else { return }
        guard let (exe, args) = Self.engineCommand() else {
            startError = "Motor bulunamadı. Uygulamayı yeniden yükleyin."
            return
        }
        let p = Process()
        p.executableURL = exe
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        p.environment = env
        let inPipe = Pipe(), outPipe = Pipe(), errPipe = Pipe()
        p.standardInput = inPipe
        p.standardOutput = outPipe
        p.standardError = errPipe
        outPipe.fileHandleForReading.readabilityHandler = { [weak self] h in
            let data = h.availableData
            Task { @MainActor in self?.receive(data) }
        }
        errPipe.fileHandleForReading.readabilityHandler = { h in
            let data = h.availableData
            if !data.isEmpty, let s = String(data: data, encoding: .utf8) {
                FileHandle.standardError.write(Data(("[motor] " + s).utf8))
            }
        }
        p.terminationHandler = { [weak self] proc in
            Task { @MainActor in self?.terminated(code: proc.terminationStatus) }
        }
        do {
            try p.run()
        } catch {
            startError = "Motor başlatılamadı: \(error.localizedDescription)"
            return
        }
        process = p
        stdin = inPipe.fileHandleForWriting
        Task {
            do {
                hello = try await call("hello", [:])
            } catch {
                startError = error.localizedDescription
            }
        }
    }

    /// Ekran görüntüleri için motorsuz örnek durum.
    func setDemo(_ h: HelloPayload) { hello = h }

    func stop() {
        process?.terminate()
        process = nil
    }

    private func terminated(code: Int32) {
        process = nil
        stdin = nil
        for (_, c) in pending {
            c.resume(throwing: EngineError(message: "Motor beklenmedik şekilde kapandı (kod \(code))."))
        }
        pending.removeAll()
        progressHandlers.removeAll()
    }

    private func receive(_ data: Data) {
        guard !data.isEmpty else { return }
        buffer.append(data)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            handle(line)
        }
    }

    private func handle(_ line: Data) {
        guard let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { return }
        let id = obj["id"] as? Int ?? -1
        if obj["event"] as? String == "progress" {
            progressHandlers[id]?(EngineProgress(
                done: obj["done"] as? Int ?? 0, total: obj["total"] as? Int ?? 0,
                message: obj["message"] as? String ?? ""))
            return
        }
        guard let cont = pending.removeValue(forKey: id) else { return }
        progressHandlers.removeValue(forKey: id)
        if obj["ok"] as? Bool == true {
            let result = obj["result"] ?? [:]
            let data = (try? JSONSerialization.data(withJSONObject: result)) ?? Data("{}".utf8)
            cont.resume(returning: data)
        } else {
            cont.resume(throwing: EngineError(
                message: obj["error"] as? String ?? "Bilinmeyen hata",
                cancelled: obj["cancelled"] as? Bool ?? false))
        }
    }

    func call<T: Decodable>(_ cmd: String, _ params: [String: Any] = [:],
                            progress: ((EngineProgress) -> Void)? = nil) async throws -> T {
        if process == nil { start() }
        guard let stdin else { throw EngineError(message: startError ?? "Motor çalışmıyor.") }
        let id = nextId
        nextId += 1
        var msg = params
        msg["id"] = id
        msg["cmd"] = cmd
        let data = try JSONSerialization.data(withJSONObject: msg) + Data([0x0A])
        let raw: Data = try await withCheckedThrowingContinuation { cont in
            pending[id] = cont
            if let progress { progressHandlers[id] = progress }
            stdin.write(data)
        }
        return try JSONDecoder().decode(T.self, from: raw)
    }

    func cancel() {
        let data = (try? JSONSerialization.data(withJSONObject: ["cmd": "cancel"])) ?? Data()
        stdin?.write(data + Data([0x0A]))
    }
}
