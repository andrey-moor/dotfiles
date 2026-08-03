#!/usr/bin/env python3
"""Minimal expect-like driver for a QEMU serial pty.

Why this exists: macOS's bundled /usr/bin/expect segfaults reliably when
using `spawn -open` on a QEMU-created pty (confirmed empirically during
Task 5 of the P2 Intune spikes -- see task-5-report-REVISED.md). This
reimplements only what's needed: drain output until quiet, optionally send
a line, and read until a marker string appears.

Used by ./arm-builder's `bootstrap` subcommand to get past the NixOS live
ISO's auto-login (as user "nixos", passwordless) and install an SSH
authorized_key into /root/.ssh, since the live ISO has no SSH access at all
until a key is installed.
"""
import argparse
import os
import select
import sys
import time


def drain_until_quiet(fd, quiet_seconds: float, max_seconds: float):
    """Read and print output until nothing arrives for `quiet_seconds`,
    or `max_seconds` total elapses."""
    start = time.time()
    last_data = time.time()
    while True:
        now = time.time()
        if now - start > max_seconds:
            print(f"\n[drain: hit max_seconds={max_seconds}]", file=sys.stderr)
            return
        if now - last_data > quiet_seconds:
            print(f"\n[drain: quiet for {quiet_seconds}s, stopping]", file=sys.stderr)
            return
        r, _, _ = select.select([fd], [], [], 0.5)
        if fd in r:
            chunk = os.read(fd, 4096)
            if chunk:
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
                last_data = time.time()


def read_until(fd, marker: bytes, timeout: float) -> bytes:
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        r, _, _ = select.select([fd], [], [], min(1.0, remaining))
        if fd in r:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buf += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
            if marker in buf:
                return buf
    raise TimeoutError(f"timed out waiting for marker {marker!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pty")
    ap.add_argument("--drain-quiet", type=float, default=None,
                     help="drain output until N seconds of silence")
    ap.add_argument("--drain-max", type=float, default=120)
    ap.add_argument("--send", default=None,
                     help="command to send; a trailing carriage return is appended")
    ap.add_argument("--marker", default=None)
    ap.add_argument("--timeout", type=float, default=240)
    args = ap.parse_args()

    fd = os.open(args.pty, os.O_RDWR | os.O_NOCTTY)

    if args.drain_quiet is not None:
        drain_until_quiet(fd, args.drain_quiet, args.drain_max)

    if args.send is not None:
        os.write(fd, (args.send + "\r").encode())

    if args.marker is not None:
        try:
            read_until(fd, args.marker.encode(), args.timeout)
            print("\n\nMARKER_FOUND", file=sys.stderr)
        except TimeoutError as e:
            print(f"\n\n{e}", file=sys.stderr)
            os.close(fd)
            sys.exit(1)

    os.close(fd)


if __name__ == "__main__":
    main()
