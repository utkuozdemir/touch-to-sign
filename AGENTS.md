# touch-to-sign — agent guide

This is the project's knowledge base for humans and agents working in this repository.
Maintain it as you go: whenever you learn something durable about how this repo works, add it here.
It is not append-only, so fix or delete anything that becomes wrong or outdated.

Keep it timeless and project-general.
Never record in-flight work or one developer's local setup here, those go into an untracked `CLAUDE.local.md`.
Prefer pointers over copies and invariants over inventories: settings, defaults and versions live in the code and the README.

There is no markdown lint in this repo, but keep one sentence per line and the first line as the single top-level heading.
`CLAUDE.md` and `GEMINI.md` just import this file, so this is the one place to edit.

## What this repo is

A `gpg.program` for git on macOS that runs gpg with the same arguments and shows a "Touch your YubiKey" popup until gpg exits.
It exists because a YubiKey signing key with a fixed touch policy waits only about 15 seconds for the touch, and a missed touch resets the card session, so the retry also asks for the PIN.

The whole program is `touch-to-sign.swift`.
The Homebrew formula and the README build it with a single `swiftc` call on that one file, so a second source file or a package dependency means changing both.

The look of the popup and the default Handoff sound are settled, so keep them unless the owner asks otherwise.

## Behavior contracts

- The popup never takes focus, so pinentry keeps the keyboard.
- The gpg exit code is passed through to git.
- `--verify` calls (one per commit in `git log --show-signature`) `execv` gpg directly, with no popup and no extra work, because they are on a hot path.
- Settings are read with `git config --get touch-to-sign.<key>`.
  git puts its own directory first in `PATH` and passes `-c` overrides down to the program, so a plain `git` lookup finds the git that started us and honors those overrides.
- The default sound is read from Apple's ToneLibrary framework at runtime and never bundled, since it is Apple's file.

## Code map and traps

- gpg is started with `posix_spawn`, because Foundation `Process` puts the child in its own process group, and Ctrl-C then leaves gpg running.
- Never call `Process.waitUntilExit` for the `git config` lookups, it added about 80 ms to every call.
- After pinentry closes, macOS hands focus to the next app in line, which is never a terminal kept out of the Dock.
  The code recognizes pinentry by its executable name, gives focus back to pinentry while its window is still on screen, and to the previously frontmost app once it is gone.

## Testing

There are no automated tests, changes are checked by building and running the binary.

- Build into a temporary directory with `swiftc -O -o /tmp/x/touch-to-sign touch-to-sign.swift`.
- Use a throwaway `GNUPGHOME` under a short `/tmp` path, since a long path overflows the gpg-agent socket path limit.
- When testing with a fake gpg script, always pin it with `git -c touch-to-sign.program=<fake>`.
  Without that, the lookup falls back to `/opt/homebrew/bin`, `/usr/local/bin` and `/usr/local/MacGPG2/bin` even with an empty `PATH`, reaches the real gpg, and a real signing call waits for a real YubiKey touch.
- A fake that exits at once finishes before the main thread builds the popup, so probes of AppKit state need a fake that sleeps about 0.3 seconds.

## Release process

Releases are made from the Actions tab: run the `release` workflow on `main` and pick which part of the version to bump.
It creates the tag and the GitHub release, with the commit titles since the previous tag as its notes, then points the formula in [utkuozdemir/homebrew-tap](https://github.com/utkuozdemir/homebrew-tap) at the new tag's tarball and its `sha256`.
The tap update needs the `PRIVATE_ACCESS_TOKEN` secret, a token with contents write access on the tap.
If only the tap update fails, re-run the failed job, which does not cut another release.

The formula builds from the tag tarball with `swiftc` on the user's Mac, so the binary is never quarantined, unlike a downloaded prebuilt binary.
Two traps when changing the formula:

- `swiftc -o bin/...` fails at link time, because the Cellar `bin` does not exist yet, so build in the source directory and `bin.install`.
- Never set `HOMEBREW_NO_INSTALL_FROM_API` when testing it, because that starts a full homebrew-core clone.

## Commit conventions

`type(scope): imperative description` titles, a prose body, and a DCO `Signed-off-by` trailer (`git commit -s`).
