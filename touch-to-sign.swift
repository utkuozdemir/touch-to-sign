// A gpg.program for git that shows a "Touch your YubiKey" HUD while gpg signs.
// The HUD never takes focus, so pinentry keeps the keyboard.
import AppKit

let args = Array(CommandLine.arguments.dropFirst())

// git puts itself first in PATH, so this is the git that started us.
func config(_ key: String) -> String? {
    let git = Process()
    git.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    git.arguments = ["git", "config", "--get", "touch-to-sign." + key]
    let out = Pipe()
    git.standardOutput = out
    guard (try? git.run()) != nil else { return nil }
    let value = String(decoding: out.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
        .trimmingCharacters(in: .newlines)
    return value.isEmpty ? nil : value
}

func findGPG() -> String? {
    if let program = config("program") { return program }
    let path = ProcessInfo.processInfo.environment["PATH"]?.split(separator: ":").map(String.init) ?? []
    // git started from a GUI app may have a minimal PATH
    let dirs = path + ["/opt/homebrew/bin", "/usr/local/bin", "/usr/local/MacGPG2/bin"]
    return dirs.map { $0 + "/gpg" }.first { FileManager.default.isExecutableFile(atPath: $0) }
}

guard let gpg = findGPG() else {
    fputs("touch-to-sign: gpg not found, set touch-to-sign.program\n", stderr)
    exit(2)
}

let argv = ([gpg] + args).map { strdup($0) } + [nil]

if args.contains("--verify") {
    execv(gpg, argv)
    perror("touch-to-sign: exec \(gpg)")
    exit(2)
}

// Unlike Process, posix_spawn keeps gpg in our process group, so Ctrl-C stops it too.
var pid: pid_t = 0
let rc = posix_spawn(&pid, gpg, nil, nil, argv, environ)
if rc != 0 {
    fputs("touch-to-sign: run \(gpg): \(String(cString: strerror(rc)))\n", stderr)
    exit(2)
}
DispatchQueue.global().async {
    var status: Int32 = 0
    while waitpid(pid, &status, 0) < 0 && errno == EINTR {}
    exit(status & 0x7f == 0 ? (status >> 8) & 0xff : 128 + (status & 0x7f))
}

// git runs gpg from the top of the work tree.
let repo = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).lastPathComponent

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let size = NSSize(width: 340, height: 72)
let panel = NSPanel(contentRect: NSRect(origin: .zero, size: size),
                    styleMask: [.nonactivatingPanel, .borderless],
                    backing: .buffered, defer: false)
panel.level = .statusBar
panel.isOpaque = false
panel.backgroundColor = .clear
panel.ignoresMouseEvents = true
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]

let blur = NSVisualEffectView(frame: NSRect(origin: .zero, size: size))
blur.material = .hudWindow
blur.state = .active
blur.wantsLayer = true
blur.layer?.cornerRadius = 18
blur.layer?.masksToBounds = true
panel.contentView = blur

let icon = NSImageView(frame: NSRect(x: 18, y: 16, width: 40, height: 40))
icon.image = NSImage(systemSymbolName: "key.horizontal.fill", accessibilityDescription: nil)?
    .withSymbolConfiguration(.init(pointSize: 28, weight: .semibold))
icon.contentTintColor = .systemYellow
icon.wantsLayer = true
blur.addSubview(icon)

let title = NSTextField(labelWithString: config("title") ?? "Touch your YubiKey")
title.font = .systemFont(ofSize: 16, weight: .semibold)
title.frame = NSRect(x: 72, y: 36, width: 256, height: 22)
blur.addSubview(title)

let sub = NSTextField(labelWithString: "Signing in \(repo)")
sub.font = .systemFont(ofSize: 12)
sub.textColor = .secondaryLabelColor
sub.lineBreakMode = .byTruncatingTail
sub.frame = NSRect(x: 72, y: 16, width: 256, height: 18)
blur.addSubview(sub)

// Top center of the screen with the mouse, just under the menu bar.
let screen = NSScreen.screens.first { NSMouseInRect(NSEvent.mouseLocation, $0.frame, false) } ?? NSScreen.main!
let vf = screen.visibleFrame
panel.setFrameOrigin(NSPoint(x: vf.midX - size.width / 2, y: vf.maxY - size.height - 12))
panel.orderFrontRegardless()

// Pulse the key icon.
let pulse = CABasicAnimation(keyPath: "opacity")
pulse.fromValue = 1.0
pulse.toValue = 0.25
pulse.duration = 0.6
pulse.autoreverses = true
pulse.repeatCount = .infinity
icon.layer?.add(pulse, forKey: "pulse")

// A file path, a system sound name or none. Glass where the Handoff alert tone is missing.
let sound = config("sound") ?? "/System/Library/PrivateFrameworks/ToneLibrary.framework/Resources/AlertTones/EncoreInfinitum/Handoff-EncoreInfinitum.caf"
if sound != "none" {
    (NSSound(contentsOfFile: sound, byReference: true) ?? NSSound(named: sound) ?? NSSound(named: "Glass"))?.play()
}

app.run()
