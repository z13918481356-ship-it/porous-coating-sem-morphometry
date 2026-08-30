from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import threading
import time
import urllib.request
from pathlib import Path


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel, resumable download of one large Zenodo file.")
    parser.add_argument("record_id")
    parser.add_argument("filename")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--migrate-from-workers", type=int,
        help="Reuse partial chunks created with this smaller worker count.",
    )
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)

    api = f"https://zenodo.org/api/records/{args.record_id}"
    request = urllib.request.Request(api, headers={"User-Agent": "SEM-morphometry-research/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        metadata = json.load(response)
    item = next(file for file in metadata["files"] if file["key"] == args.filename)
    size = int(item["size"])
    expected = item["checksum"].split(":", 1)[1]
    url = item["links"].get("content") or item["links"]["self"]
    target = args.destination / args.filename
    if target.exists() and target.stat().st_size == size and md5(target) == expected:
        print(f"Already verified: {target}")
        return

    workers = max(1, args.workers)
    chunk_size = math.ceil(size / workers)
    chunk_paths = [target.with_name(f"{target.name}.part.{index:03d}") for index in range(workers)]
    if args.migrate_from_workers:
        old_workers = args.migrate_from_workers
        if workers % old_workers:
            raise ValueError("New worker count must be a multiple of the old worker count")
        old_paths = [target.with_name(f"{target.name}.part.{index:03d}") for index in range(old_workers)]
        if not all(path.exists() for path in old_paths):
            raise FileNotFoundError("Not all old partial chunks are present for migration")
        factor = workers // old_workers
        temporary_old = [path.with_name(path.name + ".migrate") for path in old_paths]
        for old, temporary in zip(old_paths, temporary_old):
            old.replace(temporary)
        for old_index, temporary in enumerate(temporary_old):
            new_index = old_index * factor
            old_start = old_index * math.ceil(size / old_workers)
            new_start = new_index * chunk_size
            new_end = min(size - 1, (new_index + 1) * chunk_size - 1)
            if old_start != new_start:
                raise ValueError(
                    f"Unsafe migration boundary for old chunk {old_index}: "
                    f"old start {old_start}, new start {new_start}"
                )
            if temporary.stat().st_size > new_end - new_start + 1:
                raise ValueError("Old partial chunk crossed the new range boundary")
            temporary.replace(chunk_paths[new_index])
        print(f"Migrated {old_workers} partial ranges to {workers}-worker layout", flush=True)
    legacy_part = target.with_suffix(target.suffix + ".part")
    if legacy_part.exists() and not chunk_paths[0].exists():
        legacy_part.replace(chunk_paths[0])

    lock = threading.Lock()
    downloaded = sum(path.stat().st_size for path in chunk_paths if path.exists())
    next_report = (downloaded // (256 * 1024 * 1024) + 1) * 256 * 1024 * 1024
    started = time.monotonic()

    def fetch_chunk(index: int) -> None:
        nonlocal downloaded, next_report
        start = index * chunk_size
        end = min(size - 1, (index + 1) * chunk_size - 1)
        expected_length = end - start + 1
        path = chunk_paths[index]
        for attempt in range(1, 7):
            existing = path.stat().st_size if path.exists() else 0
            if existing == expected_length:
                print(f"chunk {index + 1}/{workers}: already complete", flush=True)
                return
            if existing > expected_length:
                raise ValueError(f"Chunk {index} is larger than its assigned byte range")
            range_start = start + existing
            file_request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SEM-morphometry-research/0.1",
                    "Range": f"bytes={range_start}-{end}",
                },
            )
            try:
                response = urllib.request.urlopen(file_request, timeout=180)
                if getattr(response, "status", None) != 206:
                    response.close()
                    raise RuntimeError("Zenodo did not honor the HTTP Range request")
                with response, path.open("ab") as output:
                    while True:
                        block = response.read(2 * 1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        with lock:
                            downloaded += len(block)
                            if downloaded >= next_report:
                                elapsed = max(time.monotonic() - started, 1e-6)
                                print(
                                    f"total {downloaded / 1e9:.2f}/{size / 1e9:.2f} GB "
                                    f"({100 * downloaded / size:.1f}%, {downloaded / elapsed / 1e6:.1f} MB/s)",
                                    flush=True,
                                )
                                next_report += 256 * 1024 * 1024
                if path.stat().st_size == expected_length:
                    print(f"chunk {index + 1}/{workers}: complete", flush=True)
                    return
            except Exception as exc:
                print(f"chunk {index + 1}/{workers}: retry {attempt}/6 after {type(exc).__name__}", flush=True)
                time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"Chunk {index + 1} failed after retries")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(fetch_chunk, range(workers)))

    print("Combining chunks...", flush=True)
    with legacy_part.open("wb") as output:
        for path in chunk_paths:
            with path.open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    output.write(block)
    if legacy_part.stat().st_size != size:
        raise ValueError("Combined file size does not match Zenodo metadata")
    print("Verifying MD5...", flush=True)
    actual = md5(legacy_part)
    if actual != expected:
        raise ValueError(f"Checksum mismatch: expected {expected}, found {actual}")
    legacy_part.replace(target)
    for path in chunk_paths:
        path.unlink(missing_ok=True)
    print(f"Verified {target} ({size / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
