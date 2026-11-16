// Windows arayüzünün (anonimlestirici/desktop/ui) örnek verilerle görüntüsünü alır.
//   ui_snapshot <index.html> <çıktı klasörü> [--dark]
// Görüntüler tanıtım sayfası ve README içindir; gerçek Windows'ta WebView2 aynı HTML'i çizer.
import AppKit
import WebKit

final class Shot: NSObject, WKNavigationDelegate {
    let views = ["home", "review", "result", "reverse", "settings"]
    var i = 0
    let web: WKWebView
    let window: NSWindow
    let html: URL
    let out: URL
    let suffix: String

    init(html: URL, out: URL, dark: Bool) {
        self.html = html; self.out = out; suffix = dark ? "-koyu" : ""
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: 1120, height: 720))
        window = NSWindow(contentRect: web.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        super.init()
        window.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        window.contentView = web
        web.navigationDelegate = self
    }

    func next() {
        guard i < views.count else { exit(0) }
        var c = URLComponents(url: html, resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "demo", value: views[i])]
        web.loadFileURL(c.url!, allowingReadAccessTo: html.deletingLastPathComponent())
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            let cfg = WKSnapshotConfiguration()
            cfg.snapshotWidth = 2240
            webView.takeSnapshot(with: cfg) { img, err in
                if let img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                   let png = rep.representation(using: .png, properties: [:]) {
                    try? png.write(to: self.out.appendingPathComponent("windows-\(self.views[self.i])\(self.suffix).png"))
                } else { print("hata: \(String(describing: err))") }
                self.i += 1
                self.next()
            }
        }
    }
}

let args = CommandLine.arguments
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let shot = Shot(html: URL(fileURLWithPath: args[1]).absoluteURL, out: URL(fileURLWithPath: args[2], isDirectory: true).absoluteURL, dark: args.contains("--dark"))
shot.next()
app.run()
