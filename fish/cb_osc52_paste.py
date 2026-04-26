#!/usr/bin/env python3
import base64
import os
import re
import select
import sys
import termios
import time
import tty


def read_clipboard(timeout=2):
    try:
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        except OSError:
            fd = sys.stdin.fileno()
    except (OSError, AttributeError):
        return None

    try:
        old_settings = termios.tcgetattr(fd)
    except (termios.error, OSError):
        if fd != sys.stdin.fileno():
            os.close(fd)
        return None

    try:
        tty.setraw(fd)
        os.write(fd, b"\x1b]52;c;?\x1b\\")

        start_time = time.time()
        buffer = b""

        while time.time() - start_time < timeout:
            timeout_remaining = timeout - (time.time() - start_time)
            if timeout_remaining <= 0:
                break

            try:
                rlist, _, _ = select.select([fd], [], [], min(timeout_remaining, 0.1))
            except (OSError, ValueError):
                break

            if fd in rlist:
                try:
                    data = os.read(fd, 1024)
                    if not data:
                        break
                    buffer += data

                    match = re.search(rb"\x1b]52;c;([A-Za-z0-9+/=]*)", buffer)
                    if match:
                        encoded = match.group(1).rstrip(b"\x1b\\\\")
                        try:
                            decoded = base64.b64decode(encoded).decode("utf-8")
                            return "" if decoded == " " else decoded
                        except (base64.binascii.Error, UnicodeDecodeError):
                            pass
                except OSError:
                    break

        return None

    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except (termios.error, OSError):
            pass
        if fd != sys.stdin.fileno():
            try:
                os.close(fd)
            except OSError:
                pass


if __name__ == "__main__":
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 2
    result = read_clipboard(timeout)
    if result is not None:
        print(result, end="")
        sys.exit(0)
    else:
        print("Error: Could not read from clipboard (timeout or no clipboard access)", file=sys.stderr)
        sys.exit(1)
