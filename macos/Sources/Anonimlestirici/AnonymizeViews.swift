import SwiftUI
import UniformTypeIdentifiers

struct AnonymizeView: View {
    @ObservedObject var model: AnonymizeModel

    var body: some View {
        Group {
            switch model.phase {
            case .home: HomeView(model: model)
            case .working(let title): WorkingView(title: title, progress: model.progress) { model.cancel() }
            case .review: ReviewView(model: model)
            case .result: ResultView(model: model)
            }
        }
        .alert(item: $model.alert) { a in
            Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text("Tamam")))
        }
    }
}

// MARK: - E1 Ana ekran

struct HomeView: View {
    @ObservedObject var model: AnonymizeModel
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var engine: EngineClient
    @State private var hovering = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            dropZone
            HStack(spacing: 6) {
                Text("Aranacak türler:").foregroundStyle(.secondary)
                ChipFlow(kinds: (engine.hello?.types ?? []).filter { $0.value != "ÖZEL" })
                Spacer()
                SettingsButton { Text("Değiştir…") }
            }
            if !settings.prefs.recent.isEmpty {
                Text("Son işlemler").font(.callout).foregroundStyle(.secondary)
                Table(settings.prefs.recent) {
                    TableColumn("Dosya", value: \.name)
                    TableColumn("Tarih", value: \.when).width(140)
                    TableColumn("Bulunan") { Text("\($0.found)").monospacedDigit() }.width(70)
                    TableColumn("") { item in
                        Button("Finder'da göster") { FileAccess.reveal([URL(fileURLWithPath: item.path)]) }
                            .buttonStyle(.link)
                    }.width(120)
                }
                .frame(height: 140)
            }
            HStack(spacing: 6) {
                Image(systemName: "lock.fill")
                Text(privacyNote)
            }
            .font(.callout).foregroundStyle(.secondary)
        }
        .padding(20)
    }

    private var privacyNote: String {
        #if STORE_BUILD
        return "Bu uygulama internete bağlanmaz. Dosyalarınız bu Mac'ten çıkmaz."
        #else
        return settings.prefs.llmEnabled
            ? "Dosyalarınız bu Mac'ten çıkmaz. Yerel LLM açık: metinler yalnızca \(settings.prefs.llmURL) adresine gider."
            : "Bu uygulama internete bağlanmaz. Dosyalarınız bu Mac'ten çıkmaz."
        #endif
    }

    private var dropZone: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc.text")
                .font(.system(size: 44, weight: .light))
                .foregroundStyle(.secondary)
            Text("Dosyaları buraya sürükleyin").font(.title2.weight(.semibold))
            Text(FileAccess.supported.map { "." + $0 }.joined(separator: " · ") + " · birden fazla dosya olabilir")
                .font(.callout).foregroundStyle(.secondary)
            Button("Dosya Seç…") { model.open(FileAccess.chooseFiles()) }
                .controlSize(.large)
                .keyboardShortcut("o")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .frame(minHeight: 220)
        .background(
            RoundedRectangle(cornerRadius: 14)
                .fill(hovering ? Color.accentColor.opacity(0.08) : Color(nsColor: .controlBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder(hovering ? Color.accentColor : Color.secondary.opacity(0.35),
                              style: StrokeStyle(lineWidth: 2, dash: [7, 5]))
        )
        .dropDestination(for: URL.self) { urls, _ in
            model.open(urls)
            return true
        } isTargeted: { hovering = $0 }
        .accessibilityLabel("Dosya bırakma alanı")
    }
}

struct ChipFlow: View {
    let kinds: [EntityKind]
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        ViewThatFits(in: .horizontal) {
            chips(kinds)
            chips(kinds.filter { settings.isEnabled($0) })
            Text("\(kinds.filter { settings.isEnabled($0) }.count) tür açık").foregroundStyle(.secondary)
        }
    }

    private func chips(_ list: [EntityKind]) -> some View {
        HStack(spacing: 6) {
            ForEach(list) { k in
                let on = settings.isEnabled(k)
                Button { settings.setEnabled(k, !on) } label: { chip(k.label, on) }
                    .buttonStyle(.plain)
                    .help(on ? "\(k.label) aranıyor. Kapatmak için tıklayın." : "\(k.label) aranmıyor. Açmak için tıklayın.")
                    .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }

    private func chip(_ label: String, _ on: Bool) -> some View {
                Text(label)
                    .font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Capsule().fill(on ? Color.accentColor.opacity(0.18) : .clear))
                    .overlay(Capsule().strokeBorder(on ? .clear : Color.secondary.opacity(0.4),
                                                    style: StrokeStyle(lineWidth: 1, dash: [3, 2])))
                    .foregroundStyle(on ? Color.primary : Color.secondary)
                    .fixedSize()
                    .contentShape(Capsule())
    }
}

// MARK: - E2 Tarama

struct WorkingView: View {
    let title: String
    let progress: EngineProgress?
    let cancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title).font(.title3.weight(.semibold))
            if let p = progress, p.total > 0 {
                ProgressView(value: Double(p.done), total: Double(p.total))
            } else {
                ProgressView().progressViewStyle(.linear)
            }
            Text(progress?.message ?? " ").font(.callout).foregroundStyle(.secondary).lineLimit(1)
            Button("İptal", action: cancel).keyboardShortcut(.cancelAction)
        }
        .frame(maxWidth: 520)
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - E4 Sonuç

struct ResultView: View {
    @ObservedObject var model: AnonymizeModel

    var body: some View {
        if let r = model.saved {
            VStack(alignment: .leading, spacing: 16) {
                Label("\(r.outputs.count) dosya anonimleştirildi", systemImage: "checkmark.circle.fill")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(.green)
                ForEach(r.outputs, id: \.self) { u in
                    FileRow(url: u, note: "Yapay zekâya verebileceğiniz dosya · \(u.deletingLastPathComponent().path)",
                            warn: false)
                }
                FileRow(url: r.mapping, note: "Gerçek değerleri içerir. Yapay zekâya vermeyin, paylaşmayın.", warn: true)
                HStack(spacing: 10) {
                    StatTile(value: "\(r.replaced)", label: "değiştirilen geçiş")
                    StatTile(value: "\(r.distinct)", label: "farklı değer")
                    StatTile(value: "\(r.skipped)", label: "atlanan değer")
                    StatTile(value: String(format: "%.1f sn", r.seconds).replacingOccurrences(of: ".", with: ","),
                             label: "süre")
                }
                Text("Hatırlatma: Kişinin az olduğu birimlerde “birim + unvan + tarih” birlikte kişiyi ele verebilir. Göndermeden önce anonim dosyaya bir kez göz atın.")
                    .font(.callout).foregroundStyle(.secondary)
                ForEach(r.warnings, id: \.self) { w in
                    Label(w, systemImage: "exclamationmark.triangle").font(.callout).foregroundStyle(.orange)
                }
                Spacer()
                HStack {
                    Spacer()
                    Button("Aynı kodlarla başka dosya ekle") { model.continueSameSession() }
                        .help("Bir sonraki dosyada da aynı kişi aynı kodu alır.")
                    Button("Yeni işlem") { model.newSession() }
                        .keyboardShortcut(.defaultAction)
                }
            }
            .padding(20)
        }
    }
}

struct FileRow: View {
    let url: URL
    let note: String
    let warn: Bool

    var body: some View {
        HStack(spacing: 12) {
            Text(url.pathExtension.uppercased())
                .font(.caption.weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(RoundedRectangle(cornerRadius: 7).fill(badgeColor))
            VStack(alignment: .leading, spacing: 2) {
                Text(url.lastPathComponent).fontWeight(.semibold)
                Text(note).font(.callout).foregroundStyle(warn ? Color.orange : Color.secondary).lineLimit(2)
            }
            Spacer()
            Button("Aç") { FileAccess.open(url) }
            Button("Finder'da göster") { FileAccess.reveal([url]) }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color(nsColor: .controlBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.secondary.opacity(0.2)))
    }

    private var badgeColor: Color {
        switch url.pathExtension.lowercased() {
        case "xlsx", "xlsm", "csv": return Color(red: 0.12, green: 0.48, blue: 0.27)
        case "docx": return Color(red: 0.17, green: 0.36, blue: 0.68)
        case "pptx": return Color(red: 0.72, green: 0.28, blue: 0.16)
        default: return .gray
        }
    }
}

struct StatTile: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(.title.weight(.semibold)).monospacedDigit()
            Text(label).font(.callout).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color(nsColor: .controlBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.secondary.opacity(0.2)))
    }
}

/// Ayarlar penceresini açan düğme. macOS 14 ve sonrasında Apple yalnızca SettingsLink'e izin verir;
/// macOS 13'te eski menü komutu kullanılır.
struct SettingsButton<Label: View>: View {
    @ViewBuilder let label: () -> Label

    var body: some View {
        if #available(macOS 14, *) {
            SettingsLink(label: label)
        } else {
            Button(action: {
                NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
                NSApp.activate(ignoringOtherApps: true)
            }, label: label)
        }
    }
}
