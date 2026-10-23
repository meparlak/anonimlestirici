import SwiftUI

// MARK: - E6 Ayarlar (⌘,)

private let typeHelp: [String: String] = [
    "KİŞİ": "Türkçe ad sözlüğü, unvanlar (Sayın, Dr., Bey, Hanım), sütun başlıkları ve dil modeli",
    "TC": "11 hane ve TC kimlik numarası doğrulama algoritması",
    "TELEFON": "Cep ve sabit hat, +90 / 0 önekli ya da öneksiz",
    "EPOSTA": "ad@alan.com biçimindeki adresler",
    "ADRES": "Mah., Cad., Sok., No: gibi ipuçları ve il/ilçe",
    "BİRİM": "Müdürlüğü, Daire Başkanlığı, Birimi, Bölümü… ile biten adlar",
    "KURUM": "Üniversitesi, Belediyesi, A.Ş., Ltd. Şti.… ile biten adlar ve dil modeli",
    "IBAN": "TR ile başlayan, doğrulaması tutan IBAN'lar",
    "PLAKA": "54 ABC 123 gibi araç plakaları",
    "TARİH": "12.03.1985 gibi tarihler. Analizde gerekli olabileceği için varsayılan kapalı.",
    "VERGİ": "Vergi kimlik no, MERSİS no, e-fatura ETTN (dil modeli)",
    "FİNANS": "Kart ve hesap numaraları, SWIFT kodu (dil modeli)",
    "BELGE": "Pasaport, ehliyet ve kimlik belgesi numaraları (dil modeli)",
    "IP": "IP adresleri",
    "SAĞLIK": "Hastalık, tanı, tedavi gibi sağlık bilgileri (KVKK özel nitelikli veri, dil modeli)",
    "HASSAS": "Din, etnik köken, siyasi görüş ifadeleri (KVKK özel nitelikli veri, dil modeli)",
    "ÖZEL": "Listeler sekmesinde girdiğiniz terimler",
]

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var engine: EngineClient

    var body: some View {
        TabView {
            TypesPane().tabItem { Label("Veri türleri", systemImage: "checklist") }
            ListsPane().tabItem { Label("Listeler", systemImage: "list.bullet") }
            HeadersPane().tabItem { Label("Excel başlıkları", systemImage: "tablecells") }
            OutputPane().tabItem { Label("Çıktı", systemImage: "square.and.arrow.down") }
            #if !STORE_BUILD
            LLMPane().tabItem { Label("Yerel LLM", systemImage: "cpu") }
            #endif
        }
        .frame(width: 640, height: 560)
    }
}

private struct TypesPane: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var engine: EngineClient

    var body: some View {
        Form {
            Section("Aranacak veri türleri") {
                ForEach(engine.hello?.types ?? []) { k in
                    Toggle(isOn: Binding(get: { settings.isEnabled(k) }, set: { settings.setEnabled(k, $0) })) {
                        VStack(alignment: .leading, spacing: 1) {
                            Text(k.label)
                            Text(typeHelp[k.value] ?? "").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            Section("İnce ayarlar") {
                Toggle("Dil modeli (NER) ile ikinci kontrol", isOn: $settings.prefs.nerEnabled)
                    .disabled(engine.hello?.ner != true)
                    .help(engine.hello?.ner == true ? "Uygulamanın içindeki Türkçe model, sözlükte olmayan isimleri ve KVKK veri türlerini bulur."
                                                     : "Bu pakette dil modeli yok.")
                Toggle("TC numarasında doğrulama algoritması tutmayanları atla", isOn: $settings.prefs.tcChecksum)
                Toggle("Adın ya da soyadın tek başına geçtiği yerleri de aynı kişi say (\"Ahmet Bey\", \"Yılmaz'ın\")",
                       isOn: $settings.prefs.nameAliases)
            }
        }
        .formStyle(.grouped)
    }
}

private struct ListsPane: View {
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Her satıra bir terim yazın. Her zaman anonimleştirilecek terimlerde türü \"terim | TÜR\" biçiminde verebilirsiniz (ör. \"Yılmaz Makine | KURUM\"). Tür yazmazsanız ÖZEL kabul edilir.")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                listEditor("Her zaman anonimleştir", lines: $settings.prefs.customTerms)
                listEditor("Asla anonimleştirme", lines: $settings.prefs.excludeTerms)
            }
        }
        .padding(20)
    }

    private func listEditor(_ title: String, lines: Binding<[String]>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).fontWeight(.medium)
            TextEditor(text: Binding(
                get: { lines.wrappedValue.joined(separator: "\n") },
                set: { lines.wrappedValue = $0.components(separatedBy: "\n").filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty } }
            ))
            .font(.system(.body, design: .monospaced))
            .border(Color.secondary.opacity(0.25))
        }
    }
}

private struct HeadersPane: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var engine: EngineClient
    @State private var text = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Başlığı bu listedeki gibi olan sütunlardaki bütün hücreler o türle anonimleştirilir. Böylece sözlükte olmayan isimler de kaçmaz. Her satıra \"başlık = TÜR\" yazın. Büyük/küçük harf ve Türkçe karakter fark etmez.")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            TextEditor(text: $text)
                .font(.system(.body, design: .monospaced))
                .border(Color.secondary.opacity(0.25))
                .onChange(of: text) { new in settings.prefs.headers = Self.parse(new) }
            HStack {
                Button("Varsayılana dön") {
                    settings.prefs.headers = nil
                    text = Self.format(settings.effectiveHeaders(engine.hello))
                }
                Spacer()
            }
        }
        .padding(20)
        .onAppear { text = Self.format(settings.effectiveHeaders(engine.hello)) }
    }

    static func format(_ d: [String: String]) -> String {
        d.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value < $1.value }
            .map { "\($0.key) = \($0.value)" }.joined(separator: "\n")
    }

    static func parse(_ s: String) -> [String: String] {
        var out: [String: String] = [:]
        for line in s.components(separatedBy: "\n") {
            let parts = line.components(separatedBy: "=")
            guard parts.count >= 2 else { continue }
            let k = parts.dropLast().joined(separator: "=").trimmingCharacters(in: .whitespaces)
            let v = parts.last!.trimmingCharacters(in: .whitespaces)
            if !k.isEmpty, !v.isEmpty { out[k] = v }
        }
        return out
    }
}

private struct OutputPane: View {
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        Form {
            Section("Kaydetme") {
                Picker("Çıktı klasörü", selection: $settings.prefs.askOutputFolder) {
                    Text("Her seferinde sor").tag(true)
                    Text("Hep aynı klasöre kaydet").tag(false)
                }
                .pickerStyle(.radioGroup)
                if !settings.prefs.askOutputFolder {
                    HStack {
                        Text(settings.outputFolder?.path ?? "Klasör seçilmedi")
                            .foregroundStyle(settings.outputFolder == nil ? .secondary : .primary)
                            .lineLimit(1).truncationMode(.middle)
                        Spacer()
                        Button("Seç…") {
                            settings.setOutputFolder(FileAccess.chooseFolder(
                                startingAt: settings.outputFolder, message: "Anonim dosyalar hangi klasöre kaydedilsin?",
                                prompt: "Seç"))
                        }
                    }
                }
                TextField("Dosya adı eki", text: $settings.prefs.outputSuffix)
            }
            Section("Kodlar") {
                Picker("Kod biçimi", selection: $settings.prefs.codeFormat) {
                    Text("[KİŞİ_1]").tag("bracket")
                    Text("KİŞİ_1").tag("plain")
                    Text("Kişi A").tag("letter")
                }
                Text("Unvanlar kodun dışında kalır: \"Ahmet Bey\" → \"[KİŞİ_1] Bey\". Aynı oturumda işlenen dosyalarda aynı değer hep aynı kodu alır.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            Section("Gizlilik") {
                Toggle("Belge bilgilerini temizle (yazar, son değiştiren, yorum yazarları)",
                       isOn: $settings.prefs.cleanMetadata)
            }
        }
        .formStyle(.grouped)
    }
}

#if !STORE_BUILD
private struct LLMPane: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var engine: EngineClient
    @State private var status = ""
    @State private var models: [String] = []
    @State private var pendingRemote: String?

    var body: some View {
        Form {
            Section {
                Text("Kurallarla ve dil modeliyle yakalanamayan dolaylı ifadeleri (\"müdürün eşi Gülşah\") bu bilgisayarda çalışan büyük bir dil modeli bulur. Model yalnızca öneri üretir; öneriler önizlemede \"LLM\" etiketiyle görünür ve onayınızı bekler. Ollama'nın kurulu olması gerekir (ollama.com).")
                    .font(.callout).foregroundStyle(.secondary)
                Toggle("Etkin (deneysel)", isOn: $settings.prefs.llmEnabled)
                TextField("Sunucu", text: Binding(get: { settings.prefs.llmURL }, set: { setURL($0) }))
                HStack {
                    TextField("Model", text: $settings.prefs.llmModel)
                    if !models.isEmpty {
                        Menu("Yüklü modeller") {
                            ForEach(models, id: \.self) { m in Button(m) { settings.prefs.llmModel = m } }
                        }
                        .fixedSize()
                    }
                }
                HStack {
                    Button("Bağlantıyı test et") { test() }
                    Text(status).foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .alert("Uzak sunucu", isPresented: Binding(get: { pendingRemote != nil }, set: { if !$0 { pendingRemote = nil } })) {
            Button("Vazgeç", role: .cancel) { pendingRemote = nil }
            Button("Devam et", role: .destructive) {
                settings.prefs.llmURL = pendingRemote ?? settings.prefs.llmURL
                settings.prefs.llmAllowRemote = true
                pendingRemote = nil
            }
        } message: {
            Text("\(pendingRemote ?? "") bu bilgisayarın dışında. LLM açıkken dosyalarınızdaki metinler bu sunucuya gönderilir.")
        }
    }

    private func setURL(_ url: String) {
        let host = URL(string: url)?.host ?? ""
        if ["localhost", "127.0.0.1", "::1", ""].contains(host) {
            settings.prefs.llmURL = url
            settings.prefs.llmAllowRemote = false
        } else if url != settings.prefs.llmURL {
            pendingRemote = url
        }
    }

    private func test() {
        status = "Bağlanılıyor…"
        Task {
            do {
                let r: ModelsPayload = try await engine.call("llm_models", ["url": settings.prefs.llmURL])
                models = r.models
                status = r.models.isEmpty ? "Bağlandı, ama yüklü model yok. Terminalde: ollama pull qwen2.5:3b"
                                          : "Bağlandı · \(r.models.count) model"
            } catch {
                status = "Ollama bulunamadı. Uygulama açık mı?"
            }
        }
    }
}
#endif
