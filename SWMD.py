#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import random

try:
    import requests
    from requests.adapters import HTTPAdapter  # type: ignore
    from urllib3.util import Retry  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.console import Console  # type: ignore
    from rich.theme import Theme  # type: ignore
    try:
        from win10toast import ToastNotifier  # type: ignore
    except Exception:
        ToastNotifier = None  # type: ignore
except ImportError:
    requests = None
    HTTPAdapter = None
    Retry = None
    BeautifulSoup = None
    ThreadPoolExecutor = None
    as_completed = None
    Console = None
    Theme = None
    ToastNotifier = None


STEAMCMD_DEFAULT_DIR = Path(os.getcwd()) / "steamcmd"
STEAMCMD_EXE = STEAMCMD_DEFAULT_DIR / "steamcmd.exe"
# No log file by default; can be enabled via --logfile
LOG_FILE: Path | None = None

# Colored console for professional logs
_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "green",
    "title": "bold magenta",
    "timestamp": "dim",
}) if Theme else None
console = Console(theme=_theme) if Console else None


def log(message: str, level: str = "info") -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    if console is not None:
        console.print(f"[timestamp][{timestamp}][/timestamp] {message}", style=level)
    else:
        print(line)
    if LOG_FILE is not None:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def notify(title: str, message: str) -> None:
    try:
        if ToastNotifier is not None and os.name == "nt":
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return
    except Exception:
        pass
    # Fallback to console
    log(f"{title}: {message}", level="info")


def ensure_dependencies() -> None:
    # Map of module name to pip package name
    required_modules: list[tuple[str, str]] = [
        ("requests", "requests"),
        ("bs4", "beautifulsoup4"),
        ("rich", "rich"),
        ("pyfiglet", "pyfiglet"),
        ("win10toast", "win10toast"),
    ]
    optional_modules: list[tuple[str, str]] = [
        ("lxml", "lxml"),  # optional, do not auto-install if missing
    ]

    missing: list[str] = []
    for module_name, pip_name in required_modules:
        try:
            __import__(module_name)
        except Exception:
            missing.append(pip_name)
    if missing:
        log(f"Installing Python dependencies: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        except subprocess.CalledProcessError as e:
            log(f"pip install failed: {e}")
            raise

    # Reload imports after potential installation
    global requests, BeautifulSoup, HTTPAdapter, Retry, ToastNotifier
    import importlib
    requests = importlib.import_module("requests")
    bs4_pkg = importlib.import_module("bs4")
    BeautifulSoup = getattr(bs4_pkg, "BeautifulSoup")
    try:
        HTTPAdapter = getattr(importlib.import_module("requests.adapters"), "HTTPAdapter")
    except Exception:
        HTTPAdapter = None
    try:
        Retry = getattr(importlib.import_module("urllib3.util"), "Retry")
    except Exception:
        Retry = None
    # Late import pyfiglet if present
    try:
        importlib.import_module("pyfiglet")
    except Exception:
        pass
    # Late import win10toast notifier
    try:
        ToastNotifier = getattr(importlib.import_module("win10toast"), "ToastNotifier")
    except Exception:
        ToastNotifier = None


# Neon ANSI color map for ASCII art
NEON_COLORS: dict[str, str] = {
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}


def display_ascii_art() -> None:
    """Display ASCII art with enhanced rainbow effect"""
    try:
        import pyfiglet  # type: ignore
    except Exception:
        return
    colors = [
        NEON_COLORS["bright_red"],
        NEON_COLORS["bright_green"],
        NEON_COLORS["bright_yellow"],
        NEON_COLORS["bright_blue"],
        NEON_COLORS["bright_magenta"],
        NEON_COLORS["bright_cyan"],
        NEON_COLORS["bright_white"],
    ]
    ascii_art = pyfiglet.figlet_format("SWMD", font="ANSI_Shadow")
    ascii_lines = ascii_art.split("\n")
    version_text = "by dark_byte"
    neon_color = random.choice(colors)
    vertical_position = 5
    # Right-align the signature on the widest banner width
    max_width = max((len(l) for l in ascii_lines), default=0)
    if 0 <= vertical_position < len(ascii_lines):
        ascii_lines[vertical_position] = ascii_lines[vertical_position].ljust(max_width)
    horizontal_position = max(0, max_width - len(version_text))
    if vertical_position < 0 or vertical_position >= len(ascii_lines):
        vertical_position = len(ascii_lines) - 1
    if horizontal_position < 0 or horizontal_position >= len(ascii_lines[vertical_position]):
        horizontal_position = max(0, len(ascii_lines[vertical_position]) - len(version_text))
    # Build the line by padding to the right margin, then appending the signature
    base_line = ascii_lines[vertical_position].rstrip("\n")
    padded = base_line.ljust(max_width)
    ascii_lines[vertical_position] = (
        padded + f"\u001b[1;{neon_color}m{version_text}\u001b[0m"
    )
    for line in ascii_lines:
        sys.stdout.write(f"\u001b[1;{random.choice(colors)}m{line}\u001b[0m\n")
        sys.stdout.flush()
        time.sleep(0.05)


def preferred_html_parser() -> str:
    try:
        __import__("lxml")
        return "lxml"
    except Exception:
        return "html.parser"


def build_http_session() -> "requests.Session":
    s = requests.Session()
    try:
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retries)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
    except Exception:
        pass
    s.headers.update({
        "User-Agent": "SWMD/1.0 (+https://example.local)",
    })
    return s


def restart_self() -> None:
    """Restart the current Python process with same arguments."""
    log("Restarting tool to finalize setup...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)


def find_steamcmd(explicit_path: str | None) -> Path | None:
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return p
        if (p / "steamcmd.exe").is_file():
            return p / "steamcmd.exe"
    # Environment variable override
    env_dir = os.environ.get("STEAMCMD_DIR")
    if env_dir:
        p = Path(env_dir)
        if (p / "steamcmd.exe").is_file():
            return p / "steamcmd.exe"
    # Check local folder
    if STEAMCMD_EXE.is_file():
        return STEAMCMD_EXE
    # Also support a local folder named "steam cmd" (with space)
    local_space = Path(os.getcwd()) / "steam cmd" / "steamcmd.exe"
    if local_space.is_file():
        return local_space
    # Common install locations on Windows
    candidates = [
        Path("C:/Program Files (x86)/Steam/steamcmd/steamcmd.exe"),
        Path("C:/Program Files/Steam/steamcmd/steamcmd.exe"),
        Path.home() / "AppData/Local/SteamCMD/steamcmd.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def download_steamcmd(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
    log("Downloading steamcmd...")
    session = build_http_session()
    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            tmp_path = Path(tmp.name)
    log("Extracting steamcmd...")
    shutil.unpack_archive(str(tmp_path), str(dest_dir))
    tmp_path.unlink(missing_ok=True)
    exe = dest_dir / "steamcmd.exe"
    if not exe.is_file():
        raise RuntimeError("steamcmd.exe not found after extraction")
    return exe


KNOWN_GAME_APPIDS = {
    # Commonly requested
    "Project Zomboid": "108600",
}

# IDs to exclude from download even if present in the parsed list
EXCLUDED_ITEM_IDS: set[str] = {"2872282653", "3455086119"}


def parse_workshop_url(url: str) -> dict:
    # Support: collection page or single item page or raw id
    # Extract id=######## from URL if present
    id_match = re.search(r"[?&]id=(\d+)", url)
    item_or_collection_id = id_match.group(1) if id_match else None
    is_collection = False

    log("Fetching page to resolve items...")
    session = build_http_session()
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    parser_name = preferred_html_parser()
    try:
        soup = BeautifulSoup(resp.text, parser_name)
    except Exception as e:
        # Fallback to built-in parser to avoid bs4 FeatureNotFound crashes
        log(f"Parser '{parser_name}' failed ({e}). Falling back to 'html.parser'.")
        soup = BeautifulSoup(resp.text, 'html.parser')

    # Determine if it is a collection by looking for item list
    item_links = soup.select("a[href*='steamcommunity.com/sharedfiles/filedetails/?id=']")
    item_ids = set()
    for a in item_links:
        m = re.search(r"id=(\d+)", a.get("href", ""))
        if m:
            item_ids.add(m.group(1))
    # Heuristic: collection pages list many item links, single item has itself
    if item_or_collection_id and (len(item_ids) > 1 or any(i != item_or_collection_id for i in item_ids)):
        is_collection = True

    # Fallback for collection: look for data attributes in Workshop collection pages
    if not item_ids and item_or_collection_id:
        item_ids.add(item_or_collection_id)

    # Try to detect appid (e.g., 108600 for Project Zomboid) from page
    app_id = None
    # From subscribe button sometimes has data-appid
    app_el = soup.select_one("*[data-appid]")
    if app_el and app_el.has_attr("data-appid"):
        app_id = app_el["data-appid"]
    if not app_id:
        # Try to find in scripts or links
        m = re.search(r"app/(\d+)", resp.text)
        if m:
            app_id = m.group(1)
    if not app_id:
        # Try to infer by finding a game title label on the page
        game_label = None
        # Many pages include "Game: <name>"
        for el in soup.find_all(text=re.compile(r"^\s*Game:\s*", re.I)):
            t = re.sub(r"^\s*Game:\s*", "", el, flags=re.I).strip()
            if t:
                game_label = t
                break
        if game_label and game_label in KNOWN_GAME_APPIDS:
            app_id = KNOWN_GAME_APPIDS[game_label]

    # Best-effort game name
    game_name = None
    if app_id:
        # reverse map
        for name, aid in KNOWN_GAME_APPIDS.items():
            if aid == app_id:
                game_name = name
                break
    if not game_name:
        # take found game_label if present
        try:
            game_name = game_label if game_label else None
        except NameError:
            game_name = None

    # Try to extract human-readable collection/item title
    collection_name = None
    title_el = soup.select_one('h1.workshopItemTitle') or soup.select_one('h1.collectionTitle')
    if title_el and getattr(title_el, 'get_text', None):
        collection_name = title_el.get_text(strip=True)
    if not collection_name:
        og = soup.select_one('meta[property="og:title"]')
        if og and og.has_attr('content'):
            collection_name = og['content'].strip()

    return {
        "is_collection": is_collection,
        "item_ids": sorted(item_ids),
        "app_id": app_id,
        "game_name": game_name,
        "collection_name": collection_name,
        "source_url": url,
    }


def run_steamcmd(steamcmd_exe: Path, commands: list[str], stream: bool = False, quiet: bool = False) -> dict:
    cmd = [str(steamcmd_exe)] + commands + ["+quit"]
    if not quiet:
        log(f"Running: {' '.join(commands)}")
    if stream:
        # Stream stdout/stderr live
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        collected: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            collected.append(line)
        proc.wait()
        out = "".join(collected)
        return {"returncode": proc.returncode or 0, "stdout": out, "stderr": ""}
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if not quiet:
            if stdout:
                log(stdout.rstrip())
            if stderr:
                log(stderr.rstrip())
        return {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr}


def get_game_name_from_appid(app_id: str) -> str:
    # Reverse lookup of KNOWN_GAME_APPIDS; fall back to app_id
    for name, aid in KNOWN_GAME_APPIDS.items():
        if aid == app_id:
            return name
    return app_id


def sanitize_name(name: str) -> str:
    # Remove path-unfriendly characters and trim
    safe = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    return safe or "collection"


def move_downloads_to_mods_root(steamcmd_exe: Path, app_id: str, collection_name: str | None = None) -> None:
    steam_root = Path(steamcmd_exe).parent
    src_dir = steam_root / "steamapps" / "workshop" / "content" / app_id
    if not src_dir.is_dir():
        log(f"No workshop content found for app {app_id}; nothing to move.")
        return
    mods_root = Path(os.getcwd()) / "mods"
    mods_root.mkdir(parents=True, exist_ok=True)
    game_name = get_game_name_from_appid(app_id)
    game_dir = mods_root / game_name
    if collection_name:
        game_dir = game_dir / sanitize_name(collection_name)
    dest_dir = game_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # For each workshop item directory, look for its 'mods' folder and move contents
    moved_any = False
    for item_dir in src_dir.iterdir():
        if not item_dir.is_dir():
            continue
        mods_sub = item_dir / "mods"
        if not mods_sub.is_dir():
            continue
        for child in mods_sub.iterdir():
            target_child = dest_dir / child.name
            if target_child.exists():
                # Skip duplicates
                continue
            shutil.move(str(child), str(target_child))
            moved_any = True
        # Clean up empty mods_sub and item_dir
        try:
            if mods_sub.exists() and not any(mods_sub.iterdir()):
                mods_sub.rmdir()
            if not any(item_dir.iterdir()):
                item_dir.rmdir()
        except Exception:
            pass
    # Clean up source folder if empty
    try:
        if not any(src_dir.iterdir()):
            src_dir.rmdir()
    except Exception:
        pass
    if moved_any:
        log(f"Merged new mods into {dest_dir}")


def download_items(steamcmd_exe: Path, app_id: str, item_ids: list[str], force_validate: bool = False, workers: int = 5) -> None:
    from rich.progress import Progress

    def download_one(iid: str) -> tuple[str, bool, str]:
        cmds = ["+login", "anonymous", "+workshop_download_item", app_id, iid]
        if force_validate:
            cmds += ["validate"]
        attempt = 0
        max_attempts = 3
        last_out = ""
        while attempt < max_attempts:
            result = run_steamcmd(steamcmd_exe, cmds, stream=False, quiet=True)
            out = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
            last_out = out
            if re.search(rf"Success\.\s+Downloaded item\s+{re.escape(iid)}\b", out, re.I):
                return iid, True, out
            attempt += 1
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
        return iid, False, last_out

    workers = max(1, int(workers or 1))
    results: dict[str, bool] = {}
    with Progress() as progress:
        task = progress.add_task(f"Downloading {len(item_ids)} item(s) for app {app_id}", total=len(item_ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(download_one, iid) for iid in item_ids]
            for fut in as_completed(futures):
                iid, ok, _ = fut.result()
                results[iid] = ok
                progress.advance(task, 1)

    # Suppress excluded IDs from the failure summary, but still attempted
    failed = [iid for iid, ok in results.items() if not ok and iid not in EXCLUDED_ITEM_IDS]
    if failed:
        raise RuntimeError(f"Failed to download items: {', '.join(failed)}")


def cli() -> int:
    parser = argparse.ArgumentParser(
        description="Steam Workshop Mod Downloader (SWMD): scrape Workshop page, download via steamcmd"
    )
    parser.add_argument("--url", help="Steam Workshop URL (collection or item). If omitted, you will be prompted.")
    parser.add_argument("--appid", help="Steam App ID (e.g., 108600 for Project Zomboid). If omitted, attempt to detect.")
    parser.add_argument("--steamcmd", help="Path to steamcmd.exe or its folder. If missing, it will be downloaded.")
    parser.add_argument("--output", help="Output JSON of resolved items (debug)")
    parser.add_argument("--logfile", help="Optional path to write a log file; if omitted, logs are console-only")
    parser.add_argument("--workers", type=int, default=None, help="Concurrent downloads; if omitted you'll be prompted (default: 2)")
    parser.add_argument("--validate", action="store_true", help="Pass validate for downloads")
    args = parser.parse_args()

    ensure_dependencies()

    # Enable log file only if explicitly requested
    global LOG_FILE
    LOG_FILE = Path(args.logfile).resolve() if args.logfile else None

    # Ensure steamcmd exists BEFORE asking for URL
    steamcmd_path = find_steamcmd(args.steamcmd)
    if not steamcmd_path:
        print("steamcmd not found. Attempting to download locally...")
        steamcmd_path = download_steamcmd(STEAMCMD_DEFAULT_DIR)
        # After fresh install, restart to ensure environment is clean
        restart_self()

    log(f"Using steamcmd: {steamcmd_path}")
    # Ensure steamcmd has initialized its 'package' directory by running once
    steam_root = Path(steamcmd_path).parent
    if not (steam_root / "package").is_dir():
        print("Initializing steamcmd for first-time setup...")
        _ = run_steamcmd(steamcmd_path, [], stream=True)
        # Restart so subsequent steps see a fully initialized steamcmd
        restart_self()

    # Now ask for URL/appid and proceed
    display_ascii_art()
    url = args.url or input("Enter Steam Workshop URL (collection or item): ").strip()
    if not url:
        log("No URL provided.")
        return 2

    info = parse_workshop_url(url)
    item_ids = info["item_ids"]
    app_id = args.appid or info.get("app_id")
    game_name = info.get("game_name") or get_game_name_from_appid(app_id) if app_id else None
    collection_name = info.get("collection_name")

    if not app_id:
        app_id = input("Enter Steam App ID (e.g., 108600 for Project Zomboid): ").strip()
    if not app_id:
        log("No app ID provided.")
        return 2

    if game_name:
        print(f"Game detected: {game_name}")
    if collection_name:
        print(f"Collection/Item: {collection_name}")

    if not item_ids:
        log("No workshop items found on the page.")
        return 3

    if args.output:
        Path(args.output).write_text(json.dumps(info, indent=2), encoding="utf-8")

    log(f"Resolved {len(item_ids)} item(s) for app {app_id}: {', '.join(item_ids)}")

    # Ask for concurrency if not provided
    workers = args.workers
    if workers is None:
        raw = input("Concurrent downloads (default 2): ").strip()
        workers = int(raw) if raw.isdigit() and int(raw) > 0 else 2

    download_error: Exception | None = None
    try:
        download_items(steamcmd_path, app_id, item_ids, force_validate=args.validate, workers=workers)
    except Exception as e:
        # Keep the error but continue to move whatever downloaded
        download_error = e

    # Post-process: move downloaded mods even if some items failed
    try:
        move_downloads_to_mods_root(steamcmd_path, app_id, collection_name)
    except Exception as e:
        log(f"Post-move warning: {e}")

    if download_error is not None:
        # Attempt one final retry for failed items if message lists IDs
        m = re.search(r"Failed to download items:\s*(.*)$", str(download_error))
        if m:
            retry_ids = [s.strip() for s in m.group(1).split(",") if s.strip()]
            if retry_ids:
                log("Retrying failed items one last time...", level="warning")
                try:
                    download_items(steamcmd_path, app_id, retry_ids, force_validate=args.validate, workers=min(2, workers or 1))
                    download_error = None
                except Exception as e2:
                    download_error = e2

    if download_error is not None:
        log(f"Error: {download_error}", level="error")
        notify("SWMD - Downloads finished with errors", str(download_error))
        return 4

    log("All downloads completed.", level="success")
    notify("SWMD - Downloads complete", f"Mods moved to mods/{get_game_name_from_appid(app_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(cli())


