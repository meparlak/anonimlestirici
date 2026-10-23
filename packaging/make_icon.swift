// Uygulama simgesini çizer: swift packaging/make_icon.swift <çıktı.icns>
// Koyu mavi zemin üzerinde, satırlarının bir kısmı karartılmış bir belge.
import AppKit

func draw(_ size: Int) -> NSBitmapImageRep {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                               bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = CGFloat(size) / 1024
    func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {
        NSRect(x: x * s, y: (1024 - y - h) * s, width: w * s, height: h * s)  // üstten ölçülen koordinat
    }
    let bg = NSBezierPath(roundedRect: r(100, 100, 824, 824), xRadius: 185 * s, yRadius: 185 * s)
    NSGradient(starting: NSColor(srgbRed: 0.17, green: 0.39, blue: 0.72, alpha: 1),
               ending: NSColor(srgbRed: 0.09, green: 0.23, blue: 0.45, alpha: 1))!.draw(in: bg, angle: -90)
    let (x, y, w, h, c): (CGFloat, CGFloat, CGFloat, CGFloat, CGFloat) = (300, 210, 424, 560, 110)
    let doc = NSBezierPath()
    doc.move(to: NSPoint(x: x * s, y: (1024 - y) * s))
    doc.line(to: NSPoint(x: (x + w - c) * s, y: (1024 - y) * s))
    doc.line(to: NSPoint(x: (x + w) * s, y: (1024 - y - c) * s))
    doc.line(to: NSPoint(x: (x + w) * s, y: (1024 - y - h) * s))
    doc.line(to: NSPoint(x: x * s, y: (1024 - y - h) * s))
    doc.close()
    NSColor(srgbRed: 0.97, green: 0.98, blue: 0.99, alpha: 1).setFill()
    doc.fill()
    let fold = NSBezierPath()
    fold.move(to: NSPoint(x: (x + w - c) * s, y: (1024 - y) * s))
    fold.line(to: NSPoint(x: (x + w - c) * s, y: (1024 - y - c) * s))
    fold.line(to: NSPoint(x: (x + w) * s, y: (1024 - y - c) * s))
    fold.close()
    NSColor(srgbRed: 0.79, green: 0.84, blue: 0.92, alpha: 1).setFill()
    fold.fill()
    let rows: [[(CGFloat, CGFloat, Bool)]] = [
        [(0, 0.55, false), (0.62, 0.30, true)], [(0, 0.25, true), (0.32, 0.60, false)], [(0, 0.70, false)],
        [(0, 0.38, false), (0.45, 0.42, true)], [(0, 0.60, false)],
    ]
    let lx = x + 62, ly = y + 175, lw = w - 124
    for (i, row) in rows.enumerated() {
        let yy = ly + CGFloat(i) * 66
        for (start, len, masked) in row {
            let rect = r(lx + start * lw, yy + (masked ? 0 : 12), len * lw, masked ? 44 : 20)
            (masked ? NSColor(srgbRed: 0.11, green: 0.16, blue: 0.25, alpha: 1)
                    : NSColor(srgbRed: 0.71, green: 0.76, blue: 0.85, alpha: 1)).setFill()
            NSBezierPath(roundedRect: rect, xRadius: 8 * s, yRadius: 8 * s).fill()
        }
    }
    NSGraphicsContext.restoreGraphicsState()
    return rep
}

let out = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "AppIcon.icns")
let set = FileManager.default.temporaryDirectory.appendingPathComponent("AppIcon.iconset")
try? FileManager.default.removeItem(at: set)
try! FileManager.default.createDirectory(at: set, withIntermediateDirectories: true)
for base in [16, 32, 128, 256, 512] {
    try! draw(base).representation(using: .png, properties: [:])!.write(to: set.appendingPathComponent("icon_\(base)x\(base).png"))
    try! draw(base * 2).representation(using: .png, properties: [:])!.write(to: set.appendingPathComponent("icon_\(base)x\(base)@2x.png"))
}
try! draw(1024).representation(using: .png, properties: [:])!.write(to: out.deletingPathExtension().appendingPathExtension("png"))
let p = Process()
p.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
p.arguments = ["-c", "icns", set.path, "-o", out.path]
try! p.run()
p.waitUntilExit()
print("Simge: \(out.path)")
