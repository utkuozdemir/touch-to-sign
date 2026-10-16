# gpg-touch

A `gpg.program` for git on macOS. It shows a small "Touch your YubiKey" HUD with a sound while gpg signs a commit or a tag.

The YubiKey only blinks while it waits for a touch, and the wait times out after about 15 seconds. A missed touch fails the signature, and the retry usually asks for the PIN again. The HUD makes the wait hard to miss.

- The HUD stays on top on all spaces, but it never takes focus, so pinentry keeps the keyboard.
- It shows up on the screen with the mouse, under the menu bar, with the repository name.
- It disappears as soon as gpg exits. The gpg exit code is passed through to git.
- Signature verification (`git log --show-signature`, `git verify-commit`) goes directly to gpg without a HUD.

## Install

Requires the Xcode command line tools (`xcode-select --install`) and GnuPG.

```sh
git clone https://github.com/utkuozdemir/gpg-touch.git
cd gpg-touch
mkdir -p ~/.local/bin
swiftc -O -o ~/.local/bin/gpg-touch gpg-touch.swift
git config --global gpg.program ~/.local/bin/gpg-touch
```

To update, pull and run the `swiftc` command again.

gpg is looked up in `PATH`, then in `/opt/homebrew/bin`, `/usr/local/bin` and `/usr/local/MacGPG2/bin`. Set `GPG_TOUCH_GPG` to the gpg binary to override it.

The HUD shows up on every signature. If the signing key does not require a touch, it only flashes for a moment. `ykman openpgp keys set-touch sig on` turns the touch requirement on.

## Uninstall

```sh
git config --global --unset gpg.program
rm ~/.local/bin/gpg-touch
```
