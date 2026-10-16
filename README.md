# touch-to-sign

Shows a "Touch your YubiKey" popup on macOS while git signs a commit or a tag.

The YubiKey only blinks while it waits for a touch, and it stops waiting after about 15 seconds. When the touch is missed, the signature fails, and the next try usually asks for the PIN again. The popup and its sound make the wait hard to miss.

## Install

This assumes git already signs your commits with a GPG key on a YubiKey. It needs macOS 13 or newer.

1. Install `touch-to-sign` with Homebrew. It is built from source on your Mac, which takes a second.

   ```sh
   brew install utkuozdemir/tap/touch-to-sign
   ```

2. Tell git to sign through `touch-to-sign` instead of calling gpg directly.

   ```sh
   git config --global gpg.program "$(brew --prefix)/bin/touch-to-sign"
   ```

The next signed commit shows the popup.

To update, run `brew upgrade touch-to-sign`.

<details>
<summary>Without Homebrew</summary>

Build it with the Swift compiler from the Xcode command line tools (`xcode-select --install`):

```sh
git clone https://github.com/utkuozdemir/touch-to-sign.git
cd touch-to-sign
mkdir -p ~/.local/bin
swiftc -O -o ~/.local/bin/touch-to-sign touch-to-sign.swift
git config --global gpg.program ~/.local/bin/touch-to-sign
```

To update, run `git pull` in the clone, then the `swiftc` command again.

</details>

## Settings

Nothing needs to be set. The settings live in git config, so they also apply when a GUI git client signs.

| Setting | Default | |
|---|---|---|
| `touch-to-sign.title` | `Touch your YubiKey` | The popup text. |
| `touch-to-sign.sound` | The Handoff alert tone | A sound file, a system sound name such as `Ping`, or `none` for silence. |
| `touch-to-sign.program` | `gpg`, looked up in `PATH`, `/opt/homebrew/bin`, `/usr/local/bin` and `/usr/local/MacGPG2/bin` | The gpg binary to run. |

For example:

```sh
git config --global touch-to-sign.sound none
```

Without `--global`, a setting applies only to the current repository.

## How it works

`touch-to-sign` starts gpg with the same arguments, shows the popup, and closes it when gpg exits.

- The popup stays on top on all spaces. It never takes focus, so the PIN prompt keeps the keyboard.
- It shows up on the screen with the mouse, under the menu bar, with the repository name.
- The gpg exit code is passed through to git.
- When git only checks a signature (e.g., `git log --show-signature`), gpg runs without the popup.

The popup shows up on every signature. If your key does not require a touch, it only flashes for a moment.

## Uninstall

```sh
git config --global --unset gpg.program
brew uninstall touch-to-sign
```

Without Homebrew, delete `~/.local/bin/touch-to-sign` instead.
