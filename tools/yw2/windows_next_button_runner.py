#!/usr/bin/env python3
"""
Minimal Windows desktop harness for Yo-kai Watch 2 / Busters Azahar tracing.

What it does:
- optionally launches azahar.exe with AZAHAR_YW2_* environment variables
- optionally tails an Azahar log file
- writes timing markers to a local marker log
- clicks the configured "next/proceed" button coordinate via pyautogui
- captures a screenshot before and after the click

Install:
    py -m pip install pyautogui pillow

Example:
    py tools/yw2/windows_next_button_runner.py ^
      --azahar-exe C:\\Azahar\\azahar.exe ^
      --rom D:\\roms\\yw2.3ds ^
      --azahar-log "%APPDATA%\\Azahar\\log\\azahar_log.txt" ^
      --next-x 1450 --next-y 865 ^
      --output-dir logs\\yw2_windows

If you already launched Azahar manually, omit --azahar-exe and --rom.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

try:
    import pyautogui
except ImportError as exc:
    raise SystemExit("pyautogui is required: py -m pip install pyautogui pillow") from exc


DEFAULT_ENV = {
    "AZAHAR_YW2_NWM_IPC_TRACE": "1",
    "AZAHAR_YW2_TRACE_LEVEL": "all",
    "AZAHAR_YW2_SELF_LOOPBACK": "1",
    "AZAHAR_YW2_BIND_PULSE": "0",
    "AZAHAR_YW2_STATUS_QUIET_HOST": "0",
    "AZAHAR_YW2_DUMMY_NODE": "0",
    "AZAHAR_YW2_DUMMY_PACKET": "0",
    "AZAHAR_YW2_STATUS_PULSE": "0",
    "AZAHAR_YW2_SVC_WAIT_TRACE": "0",
}

INTERESTING_LOG_TERMS = (
    "(YW2 IPC)",
    "(YW2 TRACE)",
    "(YW2 WAIT)",
    "DestroyNetwork",
    "PullPacket",
    "SendTo",
    "RecvBeacon",
    "HandleSecureData",
    "Fatal signal",
    "SIGSEGV",
    "SIGABRT",
    "SIGTRAP",
    "Assertion",
)

NOISY_TERMS = (
    "SendPacket type=0 channel=11 size=435",
    "SendPacket channel11_435",
    "Beacon self-loopback",
    "Bind event pulse",
)


def now_epoch() -> str:
    return f"{time.time():.3f}"


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_marker(path: Path, name: str) -> None:
    line = f"{now_epoch()} YW2_MARK {name}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def screenshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = pyautogui.screenshot()
    img.save(path)
    print(f"screenshot: {path}")


def tail_log(source: Path, output: Path, stop_event: Event) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"tailing: {source}")
    while not source.exists() and not stop_event.is_set():
        time.sleep(0.2)
    if stop_event.is_set():
        return

    with source.open("r", encoding="utf-8", errors="replace") as src, output.open(
        "a", encoding="utf-8"
    ) as out:
        src.seek(0, os.SEEK_END)
        while not stop_event.is_set():
            line = src.readline()
            if not line:
                time.sleep(0.05)
                continue
            if any(term in line for term in INTERESTING_LOG_TERMS) and not any(
                term in line for term in NOISY_TERMS
            ):
                tagged = f"{now_epoch()} {line}"
                out.write(tagged)
                out.flush()
                print(tagged, end="")


def launch_azahar(exe: Path, rom: str | None, extra_env: dict[str, str]) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(DEFAULT_ENV)
    env.update(extra_env)
    cmd = [str(exe)]
    if rom:
        cmd.append(rom)
    print("launch:", " ".join(cmd))
    return subprocess.Popen(cmd, env=env)


def parse_env_assignments(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--env requires NAME=VALUE, got: {value}")
        k, v = value.split("=", 1)
        parsed[k] = v
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--azahar-exe", type=Path, help="Path to azahar.exe. Omit if already running.")
    ap.add_argument("--rom", help="ROM path to pass to azahar.exe.")
    ap.add_argument("--azahar-log", type=Path, help="Azahar log file to tail.")
    ap.add_argument("--output-dir", type=Path, default=Path("logs/yw2_windows"))
    ap.add_argument("--next-x", type=int, required=True, help="Screen X coordinate for the next button.")
    ap.add_argument("--next-y", type=int, required=True, help="Screen Y coordinate for the next button.")
    ap.add_argument("--pre-click-delay", type=float, default=0.5)
    ap.add_argument("--post-click-seconds", type=float, default=8.0)
    ap.add_argument(
        "--enable-svc-wait",
        action="store_true",
        help="Set AZAHAR_YW2_SVC_WAIT_TRACE=1 before launching Azahar.",
    )
    ap.add_argument(
        "--env",
        action="append",
        default=[],
        help="Extra environment assignment for Azahar, e.g. --env AZAHAR_YW2_BIND_PULSE=1",
    )
    args = ap.parse_args()

    run_id = stamp()
    out_dir = args.output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    marker_log = out_dir / "markers.log"
    focus_log = out_dir / "azahar.focus.log"

    extra_env = parse_env_assignments(args.env)
    if args.enable_svc_wait:
        extra_env["AZAHAR_YW2_SVC_WAIT_TRACE"] = "1"

    proc: subprocess.Popen | None = None
    if args.azahar_exe:
        proc = launch_azahar(args.azahar_exe, args.rom, extra_env)

    stop_event = Event()
    tail_thread: Thread | None = None
    if args.azahar_log:
        tail_thread = Thread(target=tail_log, args=(args.azahar_log, focus_log, stop_event), daemon=True)
        tail_thread.start()

    print("Move the game to the screen with the next/proceed button.")
    input("Press Enter here to mark and click the configured coordinate...")

    screenshot(out_dir / "before_press_next.png")
    write_marker(marker_log, "BEFORE_PRESS_NEXT")
    time.sleep(args.pre_click_delay)
    pyautogui.click(args.next_x, args.next_y)
    write_marker(marker_log, "AFTER_PRESS_NEXT")
    screenshot(out_dir / "after_press_next.png")

    deadline = time.time() + args.post_click_seconds
    while time.time() < deadline:
        time.sleep(0.1)

    write_marker(marker_log, "AFTER_WAIT_WINDOW")
    screenshot(out_dir / "after_wait_window.png")

    stop_event.set()
    if tail_thread:
        tail_thread.join(timeout=1.0)

    if proc and proc.poll() is None:
        print("Azahar is still running. Leaving it open.")

    print(f"output_dir: {out_dir}")
    print(f"marker_log: {marker_log}")
    print(f"focus_log: {focus_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
