import SwiftUI

@main
struct AnonimlestiriciApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var engine: EngineClient
    @StateObject private var settings: AppSettings
    @StateObject private var anonymize: AnonymizeModel
    @StateObject private var reverse: ReverseModel

    init() {
        let engine = EngineClient()
        let settings = AppSettings()
        _engine = StateObject(wrappedValue: engine)
        _settings = StateObject(wrappedValue: settings)
        _anonymize = StateObject(wrappedValue: AnonymizeModel(engine: engine, settings: settings))
        _reverse = StateObject(wrappedValue: ReverseModel(engine: engine))
    }

    var body: some Scene {
        Window("Anonimleştirici", id: "main") {
            MainView(anonymize: anonymize, reverse: reverse)
                .environmentObject(engine)
                .environmentObject(settings)
                .onAppear {
                    engine.start()
                    delegate.engine = engine
                    delegate.open = { urls in anonymize.open(urls) }
                }
                .frame(minWidth: 860, minHeight: 600)
        }
        .defaultSize(width: 1080, height: 740)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Dosya Aç…") { anonymize.open(FileAccess.chooseFiles()) }
                    .keyboardShortcut("o")
            }
            CommandGroup(replacing: .help) {
                Link("Anonimleştirici Yardım", destination: URL(string: "https://meparlak.github.io/anonimlestirici/destek.html")!)
            }
        }

        Settings {
            SettingsView()
                .environmentObject(engine)
                .environmentObject(settings)
        }
    }
}

struct MainView: View {
    @ObservedObject var anonymize: AnonymizeModel
    @ObservedObject var reverse: ReverseModel
    @EnvironmentObject var engine: EngineClient
    @State private var tab = 0

    var body: some View {
        VStack(spacing: 0) {
            if let err = engine.startError {
                Label(err, systemImage: "exclamationmark.octagon").foregroundStyle(.red).padding()
            }
            switch tab {
            case 0: AnonymizeView(model: anonymize)
            default: ReverseView(model: reverse)
            }
        }
        .toolbar {
            ToolbarItem(placement: .principal) {
                Picker("", selection: $tab) {
                    Text("Anonimleştir").tag(0)
                    Text("Geri Çevir").tag(1)
                }
                .pickerStyle(.segmented)
                .frame(width: 260)
            }
            ToolbarItem(placement: .primaryAction) {
                SettingsButton { Image(systemName: "gearshape") }
                    .help("Ayarlar (⌘,)")
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var engine: EngineClient?
    var open: (([URL]) -> Void)?
    private var queued: [URL] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        MainActor.assumeIsolated {
            Screenshots.runIfRequested()
            SelfTest.runIfRequested()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        // Öz-test ve ekran görüntüsü modunda pencere olmadan çalışılır; uygulama kendini kapatmasın
        !CommandLine.arguments.contains("--selftest") && !CommandLine.arguments.contains("--screenshots")
    }

    /// Finder'da "Birlikte Aç" ya da Dock simgesine bırakılan dosyalar
    func application(_ application: NSApplication, open urls: [URL]) {
        if let open { open(urls) } else { queued += urls }
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        if let open, !queued.isEmpty {
            open(queued)
            queued = []
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { engine?.stop() }
        try? FileManager.default.contentsOfDirectory(at: FileManager.default.temporaryDirectory,
                                                     includingPropertiesForKeys: nil)
            .filter { $0.lastPathComponent.hasPrefix("is-") }
            .forEach { try? FileManager.default.removeItem(at: $0) }
    }
}
