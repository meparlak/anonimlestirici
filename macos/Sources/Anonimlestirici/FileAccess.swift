import AppKit
import UniformTypeIdentifiers

/// Sandbox içinde dosya erişimi.
///
/// Uygulama yalnızca kullanıcının seçtiği ya da sürüklediği dosyalara erişebilir. Motor
/// ayrı bir süreç olduğu için bu izinleri devralamaz; bu yüzden girdiler önce uygulamanın
/// kendi geçici klasörüne kopyalanır, motor orada çalışır, çıktılar da kullanıcının seçtiği
/// klasöre buradan taşınır.
enum FileAccess {
    static let supported = ["xlsx", "xlsm", "csv", "docx", "pptx", "txt", "md"]
    static let oldFormats: [String: String] = [
        "doc": "Eski Word biçimi desteklenmiyor. Dosyayı Word'de açıp \"Farklı Kaydet → .docx\" ile kaydedin.",
        "xls": "Eski Excel biçimi desteklenmiyor. Dosyayı Excel'de açıp \"Farklı Kaydet → .xlsx\" ile kaydedin.",
        "ppt": "Eski PowerPoint biçimi desteklenmiyor. Dosyayı \"Farklı Kaydet → .pptx\" ile kaydedin.",
        "pdf": "PDF henüz desteklenmiyor. Metni Word'e aktarıp .docx olarak verebilirsiniz.",
    ]

    static var contentTypes: [UTType] {
        supported.compactMap { UTType(filenameExtension: $0) }
    }

    /// Desteklenmiyorsa kullanıcıya gösterilecek açıklama.
    static func problem(with url: URL) -> String? {
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue {
            return "Klasörler desteklenmiyor, dosyaları seçin."
        }
        if url.lastPathComponent.hasPrefix("~$") {
            return "Bu, Office'in geçici kilit dosyası. Asıl dosyayı seçin."
        }
        let ext = url.pathExtension.lowercased()
        if let msg = oldFormats[ext] { return msg }
        if !supported.contains(ext) {
            return ".\(ext) dosyalar desteklenmiyor. Desteklenenler: " + supported.map { "." + $0 }.joined(separator: ", ")
        }
        return nil
    }

    /// Her iş için uygulamanın geçici klasöründe yeni bir çalışma alanı.
    static func newJobFolder() throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("is-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: url.appendingPathComponent("girdi"), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: url.appendingPathComponent("cikti"), withIntermediateDirectories: true)
        return url
    }

    /// Kullanıcının dosyasını çalışma alanına kopyalar. Aynı adlı iki dosya ayrı alt klasöre gider.
    static func copyIn(_ urls: [URL], job: URL) throws -> [URL] {
        var out: [URL] = []
        var used = Set<String>()
        for (i, src) in urls.enumerated() {
            let scoped = src.startAccessingSecurityScopedResource()
            defer { if scoped { src.stopAccessingSecurityScopedResource() } }
            var dir = job.appendingPathComponent("girdi")
            if used.contains(src.lastPathComponent) {
                dir = dir.appendingPathComponent("\(i)", isDirectory: true)
                try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            }
            used.insert(src.lastPathComponent)
            let dst = dir.appendingPathComponent(src.lastPathComponent)
            try FileManager.default.copyItem(at: src, to: dst)
            out.append(dst)
        }
        return out
    }

    /// Dosyayı hedef klasöre taşır; aynı adlı dosya varsa "ad (2).uzantı" biçiminde yeni ad verir.
    static func moveOut(_ file: URL, to folder: URL) throws -> URL {
        let fm = FileManager.default
        let stem = file.deletingPathExtension().lastPathComponent
        let ext = file.pathExtension
        var dst = folder.appendingPathComponent(file.lastPathComponent)
        var n = 2
        while fm.fileExists(atPath: dst.path) {
            dst = folder.appendingPathComponent("\(stem) (\(n))").appendingPathExtension(ext)
            n += 1
        }
        try fm.moveItem(at: file, to: dst)
        return dst
    }

    static func cleanup(_ job: URL?) {
        if let job { try? FileManager.default.removeItem(at: job) }
    }

    // MARK: Paneller

    @MainActor
    static func chooseFiles() -> [URL] {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = contentTypes
        panel.message = "Anonimleştirilecek dosyaları seçin"
        return panel.runModal() == .OK ? panel.urls : []
    }

    @MainActor
    static func chooseFolder(startingAt dir: URL?, message: String, prompt: String = "Buraya Kaydet") -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.directoryURL = dir
        panel.message = message
        panel.prompt = prompt
        return panel.runModal() == .OK ? panel.url : nil
    }

    @MainActor
    static func chooseFile(types: [UTType], message: String) -> URL? {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = types
        panel.message = message
        return panel.runModal() == .OK ? panel.url : nil
    }

    @MainActor
    static func reveal(_ urls: [URL]) {
        NSWorkspace.shared.activateFileViewerSelecting(urls)
    }

    @MainActor
    static func open(_ url: URL) {
        NSWorkspace.shared.open(url)
    }
}
