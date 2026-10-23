import SwiftUI
import UniformTypeIdentifiers

// MARK: - E5 Geri çevir

@MainActor
final class ReverseModel: ObservableObject {
    @Published var mappingName = ""
    @Published var mappingCount = 0
    @Published var input = "" { didSet { if !demo { schedule() } } }
    var demo = false
    @Published var output = AttributedString("")
    @Published var plain = ""
    @Published var status = "Önce eşleştirme tablosunu seçin."
    @Published var alert: AlertItem?

    let engine: EngineClient
    private var mappingPath: String?
    private var job: URL?
    private var task: Task<Void, Never>?

    init(engine: EngineClient) { self.engine = engine }

    func pickMapping() {
        guard let url = FileAccess.chooseFile(types: [UTType(filenameExtension: "xlsx")!],
                                              message: "…_eslestirme.xlsx dosyasını seçin") else { return }
        Task {
            do {
                FileAccess.cleanup(job)
                let job = try FileAccess.newJobFolder()
                self.job = job
                let copy = try FileAccess.copyIn([url], job: job)[0]
                let info: MappingInfo = try await engine.call("read_mapping", ["path": copy.path])
                mappingPath = copy.path
                mappingName = url.lastPathComponent
                mappingCount = info.count
                convert()
            } catch {
                alert = AlertItem(title: "Tablo okunamadı", message: error.localizedDescription)
            }
        }
    }

    private func schedule() {
        task?.cancel()
        task = Task {
            try? await Task.sleep(nanoseconds: 150_000_000)
            if !Task.isCancelled { convert() }
        }
    }

    func convert() {
        guard let mappingPath else {
            status = "Önce eşleştirme tablosunu seçin."
            return
        }
        let text = input
        Task {
            do {
                let r: ReversePayload = try await engine.call("reverse_text", ["text": text, "mappingPath": mappingPath])
                guard text == input else { return }
                plain = r.text
                output = Self.render(text, r.spans)
                status = "\(r.replaced) kod çevrildi" + (r.unknown.isEmpty
                    ? " · bilinmeyen kod yok"
                    : " · tabloda olmayan: " + r.unknown.joined(separator: ", "))
            } catch {
                status = error.localizedDescription
            }
        }
    }

    static func render(_ text: String, _ spans: [ReverseSpan]) -> AttributedString {
        let ns = text as NSString
        var out = AttributedString("")
        var pos = 0
        for s in spans.sorted(by: { $0.start < $1.start }) where s.start >= pos && s.end <= ns.length {
            out += AttributedString(ns.substring(with: NSRange(location: pos, length: s.start - pos)))
            var r = AttributedString(s.replacement)
            r.backgroundColor = Color.yellow.opacity(0.45)
            out += r
            pos = s.end
        }
        out += AttributedString(ns.substring(from: pos))
        return out
    }

    func copy() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(plain, forType: .string)
        status += " · kopyalandı"
    }

    func convertFile() {
        guard let mappingPath else {
            alert = AlertItem(title: "Eşleştirme tablosu gerekli", message: "Önce eşleştirme tablosunu seçin.")
            return
        }
        guard let src = FileAccess.chooseFile(types: FileAccess.contentTypes, message: "Geri çevrilecek dosyayı seçin")
        else { return }
        Task {
            do {
                let job = try FileAccess.newJobFolder()
                defer { FileAccess.cleanup(job) }
                let copy = try FileAccess.copyIn([src], job: job)[0]
                let r: ReverseFilePayload = try await engine.call(
                    "reverse_file",
                    ["path": copy.path, "mappingPath": mappingPath,
                     "outDir": job.appendingPathComponent("cikti").path])
                guard let folder = FileAccess.chooseFolder(startingAt: src.deletingLastPathComponent(),
                                                           message: "Geri çevrilmiş dosya nereye kaydedilsin?")
                else { return }
                let scoped = folder.startAccessingSecurityScopedResource()
                defer { if scoped { folder.stopAccessingSecurityScopedResource() } }
                let final = try FileAccess.moveOut(URL(fileURLWithPath: r.output), to: folder)
                FileAccess.reveal([final])
                status = "\(r.replaced) kod çevrildi: \(final.lastPathComponent)"
                    + (r.unknown.isEmpty ? "" : " · tabloda olmayan: " + r.unknown.joined(separator: ", "))
            } catch {
                alert = AlertItem(title: "Dosya çevrilemedi", message: error.localizedDescription)
            }
        }
    }
}

struct ReverseView: View {
    @ObservedObject var model: ReverseModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Eşleştirme tablosu:").foregroundStyle(.secondary)
                Text(model.mappingName.isEmpty ? "seçilmedi" : "\(model.mappingName) · \(model.mappingCount) kod")
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(RoundedRectangle(cornerRadius: 6).fill(Color(nsColor: .controlBackgroundColor)))
                Button("Seç…") { model.pickMapping() }
                Spacer()
                Button("Dosyadan çevir…") { model.convertFile() }
                    .help(".docx, .xlsx, .pptx, .csv, .txt dosyasını aynı biçimde geri çevirir.")
            }
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Yapay zekânın cevabı (yapıştırın)").font(.callout).foregroundStyle(.secondary)
                    TextEditor(text: $model.input)
                        .font(.body)
                        .overlay(alignment: .topLeading) {
                            if model.input.isEmpty {
                                Text("Örnek: Gecikmenin kök nedeni [BİRİM_1]'nin [KURUM_1] ile teyit sürecinin olmaması.")
                                    .foregroundStyle(.tertiary).padding(6).allowsHitTesting(false)
                            }
                        }
                        .border(Color.secondary.opacity(0.25))
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Gerçek değerlerle").font(.callout).foregroundStyle(.secondary)
                    ScrollView {
                        Text(model.output).textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .topLeading).padding(6)
                    }
                    .background(Color(nsColor: .textBackgroundColor))
                    .border(Color.secondary.opacity(0.25))
                }
            }
            HStack {
                Text(model.status).font(.callout).foregroundStyle(.secondary)
                Spacer()
                Button("Kopyala") { model.copy() }.keyboardShortcut("c", modifiers: [.command, .shift])
                    .disabled(model.plain.isEmpty)
            }
        }
        .padding(20)
        .alert(item: $model.alert) { a in
            Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text("Tamam")))
        }
    }
}
