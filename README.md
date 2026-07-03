# desktop-pet

A small desktop companion application implemented in Python that shows a cute virtual pet on your screen. Lightweight and easy to run — ideal as a learning project or a fun utility to personalize your desktop.

## Features
- Runnable pet implementation, split into focused modules (entry point: `main.py`).
- Cross-platform Python compatibility (tested on macOS).
- Simple configuration and easy extension points for animations, actions, and triggers.
- Reacts to you: dozes off when you're away (AFK), gets excited and bouncy when you type fast, and bored when you sit at the keyboard without typing.
- Pomodoro buddy: "Start Focus (25 min)" in the menu bar makes every pet settle down and work alongside you, then throw a little party when the timer ends.
- Throwable: flick-drag the pet and let go to launch it into a tumbling arc that bounces off the floor, walls, and windows before settling.
- Personality: each pet has a name and a recolourable palette — "Rename" and "Recolour" from the menu bar.
- More moods: curious and trots over to investigate, and scared if you shake him.
- Mini fetch game: "Toss a ball" drops a bouncy ball; the nearest pet chases it down and bats it around.
- Real combat: poke a pet enough and it boils over, draws a weapon, and goes into combat mode — closing to weapon range, then swinging on a windup → hit → recovery timeline with cooldowns. Each weapon plays differently (fast dagger pokes, a dashing sword slash, a long-reach spear stab, a slow heavy hammer smash, or a pistol that fires a projectile), complete with slash streaks, sparks, impact bursts, and hit markers. After enough clean hits it pounces, captures the cursor, and does a little victory dance.
- Breeding: "Breed" starts a courtship — two pets waddle together trailing hearts and a baby is born, starting tiny and growing up while inheriting a blend of its parents' colour, temperament, name, and weapon taste. Respects a cooldown and the max-pet cap.
- Removal: "Remove a pet" gives one a silly send-off (a poof, a tiny explosion, a floating ghost, or a dramatic fall); "Remove all pets…" clears the screen after a confirmation. The app stays stable and usable with zero pets — spawn more with "New pet" or "Breed".

### Project layout
- `main.py` — entry point and main loop.
- `config.py` — all tunable constants (colours, timings, behaviour chances, phrases).
- `pet.py` — the `Pet` behaviour model (state machine, physics, reactions).
- `render.py` — pixel drawing for the sprite, speech bubble, and particles.
- `overlay.py` — the transparent, always-on-top macOS overlay window (`MacOverlay`).
- `window_tracker.py` — turns on-screen windows into walkable platforms.
- `objc_bridge.py` — low-level Objective-C / ctypes plumbing.

## Requirements
- Python 3.8+
- See `requirements.txt` for Python dependencies

## Installation
1. For the easiest setup, download the latest macOS DMG from GitHub Releases, open it, and drag `Desktop Pet.app` to Applications. The release build is intended to be universal, so one download should work on both Intel and Apple Silicon Macs.

2. If macOS warns that the app is from an unidentified developer, right-click the app and choose Open once. This project is not signed or notarized.

3. To build from source yourself, clone the repo:

```
git clone https://github.com/your-username/desktop-pet.git
cd desktop-pet
```

4. Create a virtual environment (recommended) and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. To create a local release DMG without the App Store, install PyInstaller and run the build script. You can set TARGET_ARCH=universal2 on Apple Silicon if you want to try a universal build locally:

```bash
python3 -m pip install pyinstaller
./build_macos_release.sh
```

## Usage

### Simple loop (recommended): run from source
The fastest way to run the latest version is straight from this repo — no build,
no download, and **no Gatekeeper "allow" step** (that prompt only appears for the
downloaded, unsigned DMG; locally-run code is never quarantined):

```bash
./dev.sh
```

`dev.sh` pulls the latest, makes sure the virtualenv exists, stops any running
pet, and launches the fresh copy. To update after a change, just run it again.
Press Ctrl-C to quit.

It needs no Accessibility or Screen Recording permission — the pet only reads
window *bounds* and app names, and uses the no-permission idle/keystroke APIs.

### Persistent menu-bar app
For a pet that autostarts and lives in the menu bar (still built locally, so no
Gatekeeper prompt), run once:

```bash
./install_macos_app.sh
```

That installs `~/Applications/Desktop Pet.app`, which runs `main.py` from this
repo. To update it later, pull and relaunch (no rebuild needed) — or just run
`./dev.sh` again.

### Sharing it: a downloadable app that updates itself
For people who don't want anything to do with the terminal, hand them the
packaged app — it can update itself from the menu bar.

1. They download `Desktop-Pet-macOS.dmg` from the project's
   [Releases](https://github.com/wherecodegetscooked/desktop-pet/releases),
   open it, and drag the app to Applications. Because the download is unsigned,
   the **first** launch needs the one-time *System Settings → Privacy & Security
   → Open Anyway* step (right-click → Open also works).
2. After that, the paw menu has **"Check for updates…"**. It asks GitHub for the
   newest build; if there's a newer one it pops a *yes/no* dialog, and on "Update
   now" it downloads the new version, clears its quarantine flag, swaps itself
   in, and relaunches — **no re-download, no Gatekeeper prompt, no terminal.**

New versions are published automatically: every push to `main` (and every `v*`
tag) builds the app in GitHub Actions and updates a rolling `latest` release,
which is what "Check for updates" reads. (The build number is just the Actions
run number, baked into the bundle as `VERSION`.)

#### Signing (so permissions survive updates)
macOS ties a granted permission (like **Screen Recording**, which the app uses to
read window titles) to the app's code signature. PyInstaller ad-hoc signs the
app, and an ad-hoc signature is derived from the binary hash — so it **changes on
every build**. Because the updater swaps the bundle in place, macOS sees each
update as a "new" app and **re-prompts** for the permission every time.

Fix: build with a **stable** signing identity. A free self-signed certificate is
enough for permission persistence (a paid Developer ID additionally allows
notarization). One-time setup:

1. Keychain Access → *Certificate Assistant → Create a Certificate…* → name it
   e.g. `Desktop Pet Signing`, type **Code Signing**, self-signed.
2. Confirm it's usable: `security find-identity -v -p codesigning`.
3. Build signed:

   ```bash
   SIGN_IDENTITY="Desktop Pet Signing" ./build_macos_release.sh
   ```

The build pins `--identifier com.nicolaswolf.desktoppet`, so every build signed
with the same certificate shares one designated requirement and macOS keeps the
grant across updates. (The very first update onto a signed build re-prompts once,
then it sticks.) To make the *published* GitHub Actions builds persist too, the
same certificate has to be imported into the CI keychain and `SIGN_IDENTITY` set
there — otherwise CI falls back to ad-hoc.

### Developer / power-user install (run from source)
If you'd rather skip packaging, a source clone updates with a plain `git pull`.
`setup.sh` installs an autostarting menu-bar app whose **"Check for updates…"**
does `git pull` + relaunch instead of a download:

```bash
git clone https://github.com/wherecodegetscooked/desktop-pet.git && cd desktop-pet && ./setup.sh
```

This needs `git` and Python 3 (the first `git` command makes macOS offer to
install the Command Line Tools). It needs no Accessibility or Screen Recording
permission — the pet only reads window *bounds* and app names and uses the
no-permission idle/keystroke APIs.

Behavior and controls live in `pet.py` (logic) and `render.py` (visuals); tweak
`config.py` to adjust timings, colours, and phrases.

## Development
- Tweak constants in `config.py`, behaviour in `pet.py`, and visuals in `render.py`.
- Follow standard Python packaging and linting practices when expanding the project.

Running quick checks:

```bash
# run lint (if configured)
flake8 .

# run unit tests (if present)
pytest
```

## Contributing
Contributions are welcome. Please open an issue to discuss major changes before sending a pull request. For small fixes, submit a PR with a clear description of the change.

## License
This project is provided under the MIT License. See `LICENSE` for details (or add one if you want to publish).

## Acknowledgements
Inspired by tiny desktop companion projects and tutorials — a fun way to practice GUI and animation in Python.

---
If you'd like, I can:
- add a sample `LICENSE` file
- create a small GIF screenshot and add it to the README
- add basic CLI flags to `main.py` (e.g., `--scale`, `--position`)

Tell me which of these you'd like next.
