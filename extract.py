#!/usr/bin/env python3
"""Extract an Amlogic (AML) upgrade package into its component files.

Usage:
    ./aml-upgrade-package-extract.py update-usb-burning-mode.img

The package header holds a record table describing each embedded file
(bootloader, boot, system, recovery, ...), its offset and its size.
Each record is split out and written to "<name>.<ext>".
"""

import errno
import os
import struct
import sys

# Header / record-table layout
COUNT_OFFSET = 0x18        # 1 byte: number of embedded files
RECORD_TABLE_OFFSET = 0x40  # first record starts here
RECORD_SIZE = 0x240        # each record is 576 bytes

# Offsets within a single record
REC_FILE_LOC = 0x10        # big-endian uint32: offset in image
REC_FILE_SIZE = 0x18       # big-endian uint32: size in bytes
REC_EXT = 0x20             # NUL-terminated string: extension/type
REC_NAME = 0x120           # NUL-terminated string: file name


def read_cstring(buf, start, max_len):
    """Read a NUL-terminated ASCII string from buf[start:start+max_len]."""
    chunk = buf[start:start + max_len]
    end = chunk.find(b"\x00")
    if end != -1:
        chunk = chunk[:end]
    return chunk.decode("ascii", errors="replace")


def be_uint32(buf, offset):
    """Read a big-endian uint32 at offset (mirrors the C convert())."""
    return struct.unpack_from(">I", buf, offset)[0]


def extract(image_path, out_dir="."):
    with open(image_path, "rb") as fh:
        buf = fh.read()

    if len(buf) <= COUNT_OFFSET:
        raise ValueError("file too small to be a valid AML package")

    count = buf[COUNT_OFFSET]
    print(f"Found {count} file record(s) in {image_path}")

    for record in range(count):
        rec = RECORD_TABLE_OFFSET + record * RECORD_SIZE
        if rec + RECORD_SIZE > len(buf):
            print(f"WARNING: record {record} beyond end of file, stopping")
            break

        name = read_cstring(buf, rec + REC_NAME, 0x20)
        ext = read_cstring(buf, rec + REC_EXT, 0x20)
        file_loc = be_uint32(buf, rec + REC_FILE_LOC)
        file_size = be_uint32(buf, rec + REC_FILE_SIZE)

        filename = f"{name}.{ext}" if ext else name
        # Guard against path traversal / empty names from a malformed image.
        filename = os.path.basename(filename) or f"record_{record}"
        out_path = os.path.join(out_dir, filename)

        if file_loc + file_size > len(buf):
            print(f"ERROR: {filename} range [{file_loc}, +{file_size}) "
                  f"exceeds image size {len(buf)}, skipping")
            continue

        try:
            with open(out_path, "wb") as out:
                out.write(buf[file_loc:file_loc + file_size])
        except OSError as exc:
            print("ERROR: could not open output")
            print(f"the error was: {os.strerror(exc.errno)}")
            continue

        print(f"  wrote {out_path} ({file_size} bytes @ 0x{file_loc:x})")


def main(argv):
    if len(argv) <= 1:
        print(f"Usage: {argv[0]} [firmware-file-name]")
        return 0
    try:
        extract(argv[1])
    except (OSError, ValueError) as exc:
        err = getattr(exc, "errno", None)
        msg = os.strerror(err) if err == errno.ENOENT or err else str(exc)
        print(f"ERROR: {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
