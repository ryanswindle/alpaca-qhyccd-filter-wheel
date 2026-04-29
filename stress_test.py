"""
Long-running stress test for the QHYCCD filter wheel.

Mirrors Otto's observed pattern: cycles the filters [2, 3, 4, 6] back-to-back
with a configurable inter-move delay (defaults to ~5 s — much faster than
Otto's 30 s exposure cycle, so a failure burst surfaces sooner).

For each move it records whether the wheel reached the commanded position
within MOVE_TIMEOUT, and prints a one-line outcome plus a rolling summary
every SUMMARY_EVERY moves. Pair with the diagnostic NOW logging in
filter_wheel_device._read_position to correlate timeouts with stale bytes,
multi-byte responses, or junk on the serial line.

Run on the same host as the docker container:
    python stress_test.py
Ctrl-C to stop; a final summary is printed.
"""

import signal
import sys
import time

from alpaca.filterwheel import FilterWheel
from config import config


SEQUENCE = [2, 3, 4, 6]
MOVE_TIMEOUT = 75      # a bit longer than the device's 60 s internal timeout
INTER_MOVE_DELAY = 5   # seconds between completing a move and issuing the next
SUMMARY_EVERY = 20


def now() -> str:
    return time.strftime("%H:%M:%S")


def wait_for_move(fw: FilterWheel, target: int, deadline: float) -> tuple[bool, int, float]:
    """Poll Position until it equals target (or deadline elapses).

    Returns (ok, last_position, elapsed_seconds).
    """
    t0 = time.time()
    last = -1
    while time.time() < deadline:
        time.sleep(1)
        try:
            last = fw.Position
        except Exception as e:
            print(f"[{now()}]   Position GET raised: {e}")
            continue
        if last == target:
            return True, last, time.time() - t0
    return False, last, time.time() - t0


def main():
    fw = FilterWheel(f"{config.server.host}:{config.server.port}", 0)

    print(f"[{now()}] Connecting to {config.server.host}:{config.server.port}...")
    fw.Connected = True
    t0 = time.time()
    while not fw.Connected:
        time.sleep(0.1)
        if time.time() - t0 > 300:
            raise RuntimeError("Connect/homing timed out after 300 s")
    print(f"[{now()}] Connected. Initial position = {fw.Position}")

    stats = {"moves": 0, "ok": 0, "timeout": 0, "wrong_pos": 0, "rejected": 0}
    started = time.time()

    def print_summary(tag: str = "summary"):
        runtime_min = (time.time() - started) / 60
        print(
            f"[{now()}] === {tag}: {stats['moves']} moves in {runtime_min:.1f} min "
            f"| ok={stats['ok']} timeout={stats['timeout']} "
            f"wrong_pos={stats['wrong_pos']} rejected={stats['rejected']} ==="
        )

    def shutdown(signum, frame):
        print()
        print_summary("FINAL")
        try:
            fw.Connected = False
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            for target in SEQUENCE:
                stats["moves"] += 1
                t_cmd = time.time()

                try:
                    fw.Position = target
                except Exception as e:
                    stats["rejected"] += 1
                    print(f"[{now()}] -> {target}: REJECTED at command: {e}")
                    time.sleep(INTER_MOVE_DELAY)
                    continue

                ok, last_pos, elapsed = wait_for_move(fw, target, t_cmd + MOVE_TIMEOUT)
                if ok:
                    stats["ok"] += 1
                    # Quiet on success; uncomment to see every move.
                    # print(f"[{now()}] -> {target}: ok in {elapsed:.1f}s")
                elif last_pos == -1:
                    stats["timeout"] += 1
                    print(f"[{now()}] -> {target}: TIMEOUT after {elapsed:.1f}s "
                          f"(Position still -1; server-side _moving stuck or move never completed)")
                else:
                    stats["wrong_pos"] += 1
                    print(f"[{now()}] -> {target}: WRONG_POS after {elapsed:.1f}s "
                          f"(server reports Position={last_pos})")

                if stats["moves"] % SUMMARY_EVERY == 0:
                    print_summary()

                time.sleep(INTER_MOVE_DELAY)
    finally:
        print_summary("FINAL")
        try:
            fw.Connected = False
        except Exception:
            pass


if __name__ == "__main__":
    main()
