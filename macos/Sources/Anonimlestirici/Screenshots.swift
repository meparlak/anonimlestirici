import AppKit
import SwiftUI

/// App Store ekran görüntüleri: `Anonimlestirici --screenshots <klasör>` her ekranı örnek verilerle
/// 2880×1800 piksel PNG olarak çizer ve çıkar. Motor ya da gerçek dosya gerekmez.
@MainActor
enum Screenshots {
    static func runIfRequested() {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--screenshots"), i + 1 < args.count else { return }
        let dir = URL(fileURLWithPath: args[i + 1], isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        _ = NSApplication.shared
        NSApp.setActivationPolicy(.accessory)
        let dark = args.contains("--dark")
        NSApp.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)

        let engine = EngineClient()
        engine.setDemo(Demo.hello)
        let settings = AppSettings(ephemeral: true)
        settings.prefs.recent = Demo.recent
        let model = AnonymizeModel(engine: engine, settings: settings)
        model.candidates = Demo.candidates
        model.documents = ["sikayet_kayitlari_ekim.xlsx"]
        let reverse = ReverseModel(engine: engine)
        reverse.demo = true
        reverse.mappingName = "sikayet_kayitlari_ekim_eslestirme.xlsx"
        reverse.mappingCount = 9
        reverse.input = Demo.aiAnswer
        reverse.output = ReverseModel.render(Demo.aiAnswer, Demo.reverseSpans)
        reverse.plain = "…"
        reverse.status = "4 kod çevrildi · bilinmeyen kod yok"

        func shot(_ name: String, _ view: some View) {
            let root = view
                .environmentObject(engine)
                .environmentObject(settings)
            render(root, to: dir.appendingPathComponent(name + (dark ? "-koyu" : "") + ".png"))
        }

        model.phase = .home
        shot("1-ana-ekran", Frame(title: "Anonimleştirici", tab: 0) { AnonymizeView(model: model) })
        model.phase = .review
        shot("2-onizleme", Frame(title: "Anonimleştirici", tab: 0) { ReviewView(model: model) })
        model.saved = Demo.saved
        model.phase = .result
        shot("3-sonuc", Frame(title: "Anonimleştirici", tab: 0) { ResultView(model: model) })
        shot("4-geri-cevir", Frame(title: "Anonimleştirici", tab: 1) { ReverseView(model: reverse) })
        print("Ekran görüntüleri: \(dir.path)")
        exit(0)
    }

    /// 1440×900 noktalık görünümü 2× çözünürlükte (2880×1800) PNG'ye çizer.
    static func render(_ view: some View, to url: URL) {
        let size = NSSize(width: 1440, height: 900)
        let host = NSHostingView(rootView: view.frame(width: size.width, height: size.height))
        host.frame = NSRect(origin: .zero, size: size)
        let window = NSWindow(contentRect: host.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        window.contentView = host
        window.appearance = NSApp.appearance
        host.layoutSubtreeIfNeeded()
        RunLoop.current.run(until: Date().addingTimeInterval(0.4))
        host.layoutSubtreeIfNeeded()
        guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 2880, pixelsHigh: 1800,
                                         bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                         colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return }
        rep.size = size
        host.cacheDisplay(in: host.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }
}

/// Ekran görüntüsünde pencere başlığını ve araç çubuğunu taklit eden çerçeve.
private struct Frame<Content: View>: View {
    let title: String
    let tab: Int
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                HStack(spacing: 8) {
                    Circle().fill(Color(red: 1, green: 0.37, blue: 0.34)).frame(width: 12, height: 12)
                    Circle().fill(Color(red: 1, green: 0.74, blue: 0.18)).frame(width: 12, height: 12)
                    Circle().fill(Color(red: 0.16, green: 0.78, blue: 0.25)).frame(width: 12, height: 12)
                    Spacer()
                    if tab >= 0 { Image(systemName: "gearshape").foregroundStyle(.secondary) }
                }
                if tab >= 0 {
                    Picker("", selection: .constant(tab)) {
                        Text("Anonimleştir").tag(0)
                        Text("Geri Çevir").tag(1)
                    }
                    .pickerStyle(.segmented).frame(width: 260)
                } else {
                    Text(title).fontWeight(.semibold)
                }
            }
            .padding(.horizontal, 16).frame(height: 52)
            .background(Color(nsColor: .windowBackgroundColor))
            Divider()
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

/// Ekran görüntülerinde kullanılan uydurma örnek veriler.
private enum Demo {
    static let types: [(String, String, Bool)] = [
        ("KİŞİ", "Ad soyad", true), ("TC", "TC kimlik no", true), ("TELEFON", "Telefon", true),
        ("EPOSTA", "E-posta", true), ("ADRES", "Adres", true), ("BİRİM", "Birim", true), ("KURUM", "Kurum", true),
        ("IBAN", "IBAN", true), ("PLAKA", "Plaka", false), ("TARİH", "Tarih", false),
        ("VERGİ", "Vergi/MERSİS no", true), ("FİNANS", "Kart/hesap no", true), ("BELGE", "Belge no", true),
        ("IP", "IP adresi", true), ("SAĞLIK", "Sağlık bilgisi", true), ("HASSAS", "Din/etnik/siyasi", true),
        ("ÖZEL", "Özel liste", true),
    ]
    static let hello = HelloPayload(
        version: "0.2.0", ner: true,
        types: types.map { EntityKind(value: $0.0, label: $0.1, defaultEnabled: $0.2) },
        defaults: EngineDefaults(headers: ["ad soyad": "KİŞİ", "tc kimlik no": "TC", "telefon": "TELEFON",
                                           "e-posta": "EPOSTA", "birim": "BİRİM", "firma": "KURUM"]))

    static let recent = [
        RecentItem(name: "uygunsuzluk_kayitlari_eylul_anonim.xlsx", path: "/tmp/a", when: "20.10.2026 14:12", found: 84),
        RecentItem(name: "ic_denetim_raporu_anonim.docx", path: "/tmp/b", when: "18.10.2026 09:40", found: 31),
    ]

    static func c(_ id: Int, _ type: String, _ label: String, _ value: String, _ code: String, _ count: Int,
                  _ source: String, low: Bool = false, accepted: Bool = true, ctx: String = "", variants: [String] = []) -> Candidate {
        let context = ctx.isEmpty ? value : ctx
        let r = (context as NSString).range(of: value)
        return Candidate(id: id, type: type, typeLabel: label, value: value, variants: variants,
                         code: accepted ? code : "", count: count, accepted: accepted, lowConfidence: low,
                         confidence: low ? 0.4 : 0.9, sources: [source], files: ["sikayet_kayitlari_ekim.xlsx"],
                         occurrences: [Occurrence(file: "sikayet_kayitlari_ekim.xlsx", location: "Ekim!E2", context: context,
                                                  start: r.location, end: r.location + r.length)])
    }

    static let candidates = [
        c(1, "KİŞİ", "Ad soyad", "Ahmet Yılmaz", "[KİŞİ_1]", 3, "Sütun başlığı, Ad sözlüğü",
          ctx: "Ahmet Yılmaz siparişin 2 hafta geciktiğini, satın almaya ulaşamadığını söyledi.", variants: ["AHMET YILMAZ", "Ahmet"]),
        c(2, "TELEFON", "Telefon", "0532 123 45 67", "[TELEFON_1]", 1, "Kalıp"),
        c(3, "BİRİM", "Birim", "Satın Alma Birimi", "[BİRİM_1]", 4, "Sonek kalıbı"),
        c(4, "KİŞİ", "Ad soyad", "Ayşe Kaya", "[KİŞİ_2]", 2, "NER modeli, Ad sözlüğü"),
        c(5, "KURUM", "Kurum", "Yıldız Makine A.Ş.", "[KURUM_1]", 2, "Sonek kalıbı, NER modeli"),
        c(6, "TC", "TC kimlik no", "10000000078", "[TC_1]", 1, "Kalıp"),
        c(7, "SAĞLIK", "Sağlık bilgisi", "bel fıtığı ameliyatı", "[SAĞLIK_1]", 1, "NER modeli"),
        c(8, "EPOSTA", "E-posta", "a.yilmaz@ornek.com.tr", "[EPOSTA_1]", 1, "Kalıp"),
        c(9, "ADRES", "Adres", "Esentepe Mah. Üniversite Cad. No:12 Serdivan/Sakarya", "[ADRES_1]", 1, "Adres ipuçları"),
        c(10, "KİŞİ", "Ad soyad", "Umut", "", 1, "Ad sözlüğü", low: true, accepted: false,
          ctx: "Umut ediyoruz ki sorun bu hafta çözülür."),
    ]

    static let saved = SavedResult(
        outputs: [URL(fileURLWithPath: "/Users/ornek/Belgeler/Kalite/sikayet_kayitlari_ekim_anonim.xlsx")],
        mapping: URL(fileURLWithPath: "/Users/ornek/Belgeler/Kalite/sikayet_kayitlari_ekim_eslestirme.xlsx"),
        replaced: 16, distinct: 9, skipped: 1, seconds: 0.8, warnings: [])

    static let aiAnswer = "Kök neden: [BİRİM_1] ile [KURUM_1] arasında teslim tarihi teyit süreci yok. [KİŞİ_1]'in şikâyeti ikinci kez geldi. Öneri: [KİŞİ_2] haftalık tedarikçi toplantısını yönetsin."
    static var reverseSpans: [ReverseSpan] {
        let ns = aiAnswer as NSString
        return [("[BİRİM_1]", "Satın Alma Birimi"), ("[KURUM_1]", "Yıldız Makine A.Ş."),
                ("[KİŞİ_1]", "Ahmet Yılmaz"), ("[KİŞİ_2]", "Ayşe Kaya")].map { code, value in
            let r = ns.range(of: code)
            return ReverseSpan(start: r.location, end: r.location + r.length, replacement: value)
        }
    }
}
