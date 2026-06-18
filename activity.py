"""Classify what the human is doing into a pet reaction.

Pure policy with no platform code: given the frontmost app (bundle id / name),
the frontmost window title, and whether sound is currently playing, decide
which prop the pet should show. The detection plumbing lives in `overlay.py`
(foreground app/title) and `playback.py` (audio + music play state); this
module holds only the lookup tables, so adding a new app is a one-line edit.

Reactions:
  "work"   -> works on a laptop and types (focus session, editors, IDEs,
              terminals, office / notes apps)
  "video"  -> munches popcorn (a video player or a YouTube-style browser tab —
              only while audio is actually playing)
  "gaming" -> sparkles with excitement (games / Steam)
  None     -> no special prop

Music headphones are handled separately (see playback.py): they show only while
Spotify / Apple Music is actually playing, layered on top of any prop above.
"""

BROWSER_BUNDLES = {
    "com.apple.Safari",
    "com.google.Chrome",
    "com.google.Chrome.canary",
    "org.mozilla.firefox",
    "com.microsoft.edgemac",
    "com.brave.Browser",
    "company.thebrowser.Browser",  # Arc
    "com.operasoftware.Opera",
    "com.vivaldi.Vivaldi",
    "app.zen-browser.zen",
}

VIDEO_BUNDLES = {
    "com.apple.QuickTimePlayerX",
    "com.colliderli.iina",
    "org.videolan.vlc",
    "com.apple.TV",
    "com.netflix.Netflix",
    "com.plexapp.plex",
}

WORK_BUNDLES = {
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
    "com.todesktop.230313mzl4w4u92",  # Cursor
    "com.apple.dt.Xcode",
    "com.sublimetext.4",
    "com.sublimetext.3",
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "dev.warp.Warp-Stable",
    "com.jetbrains.intellij",
    "com.jetbrains.pycharm",
    "com.jetbrains.WebStorm",
    "com.jetbrains.goland",
    "com.microsoft.Word",
    "com.microsoft.Excel",
    "com.microsoft.Powerpoint",
    "com.apple.iWork.Pages",
    "com.apple.iWork.Numbers",
    "com.apple.iWork.Keynote",
    "com.apple.Notes",
    "notion.id",
    "md.obsidian",
    "com.figma.Desktop",
    "com.adobe.Photoshop",
}

GAME_BUNDLES = {
    "com.valvesoftware.steam",
    "com.valvesoftware.steam.helper",
    "com.epicgames.launcher",
}

# Substring fallbacks on the lowercased app name, used when the bundle id is
# missing or unrecognised.
WORK_NAME_HINTS = (
    "code", "xcode", "terminal", "iterm", "warp", "intellij", "pycharm",
    "webstorm", "goland", "vim", "emacs", "word", "pages", "notion",
    "obsidian", "figma", "sublime",
)
VIDEO_NAME_HINTS = ("quicktime", "vlc", "iina", "netflix", "plex", "infuse")
GAME_NAME_HINTS = ("steam", "epic games", "minecraft")
BROWSER_NAME_HINTS = (
    "safari", "chrome", "firefox", "edge", "brave", "arc", "opera", "vivaldi", "zen"
)

# Matched against the lowercased browser window title to spot a video tab.
VIDEO_TITLE_KEYWORDS = (
    "youtube", "netflix", "vimeo", "twitch", "hulu", "disney", "prime video",
    "hbo", "crunchyroll", "- video",
)


def needs_title(bundle, app_name):
    """Whether classify() needs the frontmost window title for this app.

    Only browsers do (to tell a video tab from ordinary browsing), so we skip
    the window-list peek otherwise.
    """
    name = (app_name or "").lower()
    return bundle in BROWSER_BUNDLES or any(h in name for h in BROWSER_NAME_HINTS)


def _matches(bundle, app_name, bundles, name_hints):
    if bundle and bundle in bundles:
        return True
    name = (app_name or "").lower()
    return any(hint in name for hint in name_hints)


def classify(bundle, app_name, window_title, focus_active, audio_playing):
    """Return the foreground prop context: "work" | "video" | "gaming" | None.

    A focus session always means "work". Video (a video app or a YouTube-style
    browser tab) only counts while `audio_playing` is True, so a paused video
    doesn't get popcorn. Music headphones are decided separately by the caller.
    """
    if focus_active:
        return "work"
    if _matches(bundle, app_name, VIDEO_BUNDLES, VIDEO_NAME_HINTS):
        return "video" if audio_playing else None
    if _matches(bundle, app_name, GAME_BUNDLES, GAME_NAME_HINTS):
        return "gaming"
    if _matches(bundle, app_name, WORK_BUNDLES, WORK_NAME_HINTS):
        return "work"
    if needs_title(bundle, app_name) and audio_playing:
        title = (window_title or "").lower()
        if any(keyword in title for keyword in VIDEO_TITLE_KEYWORDS):
            return "video"
    return None
