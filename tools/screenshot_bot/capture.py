#!/usr/bin/env python3
"""
SBU documentation screenshot bot (Playwright).

Modes:
  login   — open browser; log in to Odoo manually; save session to auth.json
  run     — visit every URL in capture_plan.json and save PNGs
  manual  — browse freely; press Enter in the terminal to capture current page
  watch   — auto-capture when the browser URL changes (documentation walkthrough)

Setup (once):
  pip install playwright
  playwright install chromium

Examples:
  cd my-odoo
  python tools/screenshot_bot/capture.py login
  copy tools\\screenshot_bot\\capture_plan.example.json tools\\screenshot_bot\\capture_plan.json
  python tools/screenshot_bot/capture.py run
  python tools/screenshot_bot/capture.py manual
  python tools/screenshot_bot/capture.py watch
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install Playwright: pip install playwright", file=sys.stderr)
    print("Then: playwright install chromium", file=sys.stderr)
    sys.exit(1)

BOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = BOT_DIR.parents[1]
AUTH_FILE = BOT_DIR / "auth.json"
DEFAULT_PLAN = BOT_DIR / "capture_plan.json"
EXAMPLE_PLAN = BOT_DIR / "capture_plan.example.json"


def load_plan(path: Path) -> dict:
    if not path.is_file():
        print(f"Missing plan file: {path}", file=sys.stderr)
        print(f"Copy example: {EXAMPLE_PLAN}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_output_dir(plan: dict) -> Path:
    out = Path(plan.get("output_dir", "docs/guide/screenshots"))
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    return out


def build_url(base_url: str, path: str) -> str:
    path = (path or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def safe_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return f"capture-{int(time.time())}.png"
    if not name.lower().endswith(".png"):
        name += ".png"
    return re.sub(r'[<>:"/\\|?*]', "-", name)


def run_login(base_url: str, headless: bool) -> None:
    print(f"Opening {base_url} — log in, then press Enter here to save session…")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)
        input(">>> Press Enter after you are logged in and see the Odoo home… ")
        context.storage_state(path=str(AUTH_FILE))
        browser.close()
    print(f"Session saved: {AUTH_FILE}")


def new_context(playwright, plan: dict, use_auth: bool):
    viewport = plan.get("viewport") or {"width": 1440, "height": 900}
    kwargs = {"viewport": viewport}
    if use_auth and AUTH_FILE.is_file():
        kwargs["storage_state"] = str(AUTH_FILE)
    elif use_auth:
        print("Warning: auth.json missing — run: python capture.py login", file=sys.stderr)
    return playwright.chromium.launch(headless=plan.get("headless", False)).new_context(**kwargs)


def capture_page(page, outfile: Path, full_page: bool) -> None:
    page.wait_for_load_state("networkidle", timeout=60_000)
    page.screenshot(path=str(outfile), full_page=full_page)
    print(f"  saved {outfile.relative_to(REPO_ROOT)}")


def run_batch(plan: dict, plan_path: Path) -> None:
    base_url = plan.get("base_url", "").strip()
    if not base_url:
        print("capture_plan.json needs base_url", file=sys.stderr)
        sys.exit(1)
    out_dir = resolve_output_dir(plan)
    shots = plan.get("shots") or []
    if not shots:
        print("No shots in plan.", file=sys.stderr)
        sys.exit(1)

    print(f"Plan: {plan_path.name} | {len(shots)} shots | output: {out_dir.relative_to(REPO_ROOT)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=plan.get("headless", False))
        context = browser.new_context(
            viewport=plan.get("viewport") or {"width": 1440, "height": 900},
            storage_state=str(AUTH_FILE) if AUTH_FILE.is_file() else None,
        )
        page = context.new_page()
        default_wait = int(plan.get("default_wait_ms", 2500))

        for i, shot in enumerate(shots, 1):
            file_name = safe_filename(shot.get("file") or f"shot-{i:02d}.png")
            url = build_url(base_url, shot.get("path") or shot.get("url") or "")
            use_auth = shot.get("auth", True)
            if not use_auth:
                # Fresh context without cookies for login page
                page.close()
                ctx = browser.new_context(
                    viewport=plan.get("viewport") or {"width": 1440, "height": 900},
                )
                page = ctx.new_page()
            elif not AUTH_FILE.is_file():
                print("  (no auth.json — page may redirect to login)")

            print(f"[{i}/{len(shots)}] {file_name}")
            if shot.get("comment"):
                print(f"       {shot['comment']}")
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(int(shot.get("wait_ms", default_wait)))
            capture_page(page, out_dir / file_name, bool(shot.get("full_page", False)))

            if not use_auth:
                page.close()
                page = context.new_page()

        browser.close()
    print("Done.")


def run_manual(plan: dict) -> None:
    out_dir = resolve_output_dir(plan)
    base_url = plan.get("base_url", "https://pignatelli111-my-odoo.odoo.com")
    print("Manual mode — navigate in the browser.")
    print("  Enter = screenshot current page (asks filename)")
    print("  q     = quit")
    print(f"  Output folder: {out_dir.relative_to(REPO_ROOT)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=plan.get("viewport") or {"width": 1440, "height": 900},
            storage_state=str(AUTH_FILE) if AUTH_FILE.is_file() else None,
        )
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)

        while True:
            cmd = input("Filename (e.g. 28-purchase-request.png) or [q]uit: ").strip()
            if cmd.lower() in ("q", "quit", "exit"):
                break
            if not cmd:
                print("  skipped")
                continue
            outfile = out_dir / safe_filename(cmd)
            try:
                capture_page(page, outfile, full_page=False)
            except Exception as exc:
                print(f"  error: {exc}")

        if AUTH_FILE.parent.exists():
            save = input("Save login session to auth.json? [y/N]: ").strip().lower()
            if save == "y":
                context.storage_state(path=str(AUTH_FILE))
                print(f"Saved {AUTH_FILE}")
        browser.close()


def run_watch(plan: dict) -> None:
    """Screenshot whenever you change URL in the browser (good for doc walkthrough)."""
    out_dir = resolve_output_dir(plan)
    base_url = plan.get("base_url", "https://pignatelli111-my-odoo.odoo.com")
    host = urlparse(base_url).netloc
    counter = [0]

    print("Watch mode — each navigation on the same site triggers a screenshot.")
    print("  Close the browser window to stop.")
    print(f"  Host filter: {host}")
    print(f"  Output: {out_dir.relative_to(REPO_ROOT)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=plan.get("viewport") or {"width": 1440, "height": 900},
            storage_state=str(AUTH_FILE) if AUTH_FILE.is_file() else None,
        )
        page = context.new_page()

        def on_navigate(frame):
            if frame != page.main_frame:
                return
            url = page.url
            if host and host not in url:
                return
            counter[0] += 1
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path.strip("/"))[:60] or "home"
            name = safe_filename(f"watch-{counter[0]:03d}-{slug}.png")
            page.wait_for_timeout(1500)
            try:
                capture_page(page, out_dir / name, full_page=False)
            except Exception as exc:
                print(f"  capture failed: {exc}")

        page.on("framenavigated", on_navigate)
        page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)
        input(">>> Browse Odoo; screenshots on each URL change. Press Enter here to stop… ")

        try:
            context.storage_state(path=str(AUTH_FILE))
        except Exception:
            pass
        browser.close()
    print("Watch ended.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SBU Odoo screenshot bot")
    parser.add_argument(
        "mode",
        choices=("login", "run", "manual", "watch"),
        help="login=save session; run=batch plan; manual=Enter to shoot; watch=on URL change",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN,
        help=f"JSON plan path (default: {DEFAULT_PLAN.name})",
    )
    parser.add_argument("--base-url", help="Override base_url for login mode")
    parser.add_argument("--headless", action="store_true", help="Headless browser (run mode only)")
    args = parser.parse_args()

    plan = {}
    if args.plan.is_file():
        plan = load_plan(args.plan)
    elif args.mode != "login":
        plan = {"base_url": "https://pignatelli111-my-odoo.odoo.com", "output_dir": "docs/guide/screenshots"}

    if args.mode == "login":
        base = args.base_url or plan.get("base_url") or "https://pignatelli111-my-odoo.odoo.com"
        run_login(base, headless=args.headless)
    elif args.mode == "run":
        if args.headless:
            plan["headless"] = True
        run_batch(plan, args.plan)
    elif args.mode == "manual":
        run_manual(plan)
    elif args.mode == "watch":
        run_watch(plan)


if __name__ == "__main__":
    main()
