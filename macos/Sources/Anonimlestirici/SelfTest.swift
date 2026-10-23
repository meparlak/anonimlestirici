import AppKit

/// `Anonimlestirici --selftest`: paketlenmiş uygulamanın sandbox içinde motoru başlatıp örnek bir
/// dosyayı tarayabildiğini, kaydedebildiğini ve geri çevirebildiğini denetler. Sonucu standart
/// çıktıya yazar ve çıkış kodu 0 (başarılı) ya da 1 ile kapanır.
@MainActor
enum SelfTest {
    static func runIfRequested() {
        guard CommandLine.arguments.contains("--selftest") else { return }
        say("öz-test başlıyor")
        NSApp.windows.forEach { $0.orderOut(nil) }
        Task { exit(await run() ? 0 : 1) }
    }

    private static func say(_ s: String) {
        FileHandle.standardOutput.write(Data((s + "\n").utf8))
    }

    private static func run() async -> Bool {
        let engine = EngineClient()
        engine.start()
        do {
            let hello: HelloPayload = try await engine.call("hello")
            say("motor: \(hello.version), dil modeli: \(hello.ner ? "var" : "yok"), \(hello.types.count) tür")
            let job = try FileAccess.newJobFolder()
            let src = job.appendingPathComponent("ornek.txt")
            try """
            Toplantı notu
            Kıvılcım Aras ile John Smith toplantıya katıldı; Yıldız Makine A.Ş. temsilcisi de oradaydı.
            Ahmet Yılmaz (TC: 10000000078, Tel: 0532 123 45 67) Satın Alma Birimi adına konuştu.
            """.write(to: src, atomically: true, encoding: .utf8)
            let copies = try FileAccess.copyIn([src], job: job)
            let settings = AppSettings(ephemeral: true)
            let _: Empty = try await engine.call("configure", ["settings": settings.engineSettings(hello)])
            let res: AnalysisPayload = try await engine.call("analyze", ["paths": copies.map(\.path)])
            for c in res.candidates {
                say("  \(c.accepted ? "x" : " ") \(c.code.padding(toLength: 13, withPad: " ", startingAt: 0)) \(c.value)  [\(c.sources.joined(separator: ", "))]")
            }
            let saved: SavePayload = try await engine.call("save", ["outDir": job.appendingPathComponent("cikti").path])
            let out = try String(contentsOfFile: saved.outputs[0], encoding: .utf8)
            say("anonim çıktı:\n" + out)
            let _: MappingInfo = try await engine.call("read_mapping", ["path": saved.mapping])
            let back: ReversePayload = try await engine.call("reverse_text", ["text": out, "mappingPath": saved.mapping])
            let ok = back.text.contains("Kıvılcım Aras") && back.text.contains("10000000078") && !out.contains("Ahmet")
            say(ok ? "SONUÇ: BAŞARILI" : "SONUÇ: BAŞARISIZ\n" + back.text)
            FileAccess.cleanup(job)
            engine.stop()
            return ok
        } catch {
            say("SONUÇ: HATA \(error.localizedDescription)")
            return false
        }
    }
}
