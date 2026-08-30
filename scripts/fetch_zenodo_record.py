from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify every file in a public Zenodo record.")
    parser.add_argument("record_id")
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--include", action="append", default=[],
        help="Download only filenames matching this glob; repeat for multiple patterns.",
    )
    args = parser.parse_args()

    args.destination.mkdir(parents=True, exist_ok=True)
    api_url = f"https://zenodo.org/api/records/{args.record_id}"
    request = urllib.request.Request(api_url, headers={"User-Agent": "SEM-morphometry-research/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        metadata = json.load(response)
    (args.destination / "zenodo_record_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    selected = [
        item for item in metadata.get("files", [])
        if not args.include or any(fnmatch.fnmatch(item["key"], pattern) for pattern in args.include)
    ]
    if not selected:
        raise ValueError(f"No Zenodo files matched include patterns: {args.include}")
    manifest = []
    for index, item in enumerate(selected, 1):
        filename = item["key"]
        target = args.destination / filename
        algorithm, expected = item["checksum"].split(":", 1)
        status = "downloaded"
        if target.exists() and digest(target, algorithm) == expected:
            status = "already_verified"
        else:
            url = item["links"].get("content") or item["links"].get("self")
            if not url:
                raise KeyError(f"No downloadable content link for {filename}")
            temporary = target.with_suffix(target.suffix + ".part")
            print(f"[{index}/{len(selected)}] downloading {filename} ({item['size'] / 1e6:.1f} MB)", flush=True)
            file_request = urllib.request.Request(url, headers={"User-Agent": "SEM-morphometry-research/0.1"})
            existing = temporary.stat().st_size if temporary.exists() else 0
            if existing:
                file_request.add_header("Range", f"bytes={existing}-")
            response = urllib.request.urlopen(file_request, timeout=120)
            resume_accepted = existing > 0 and getattr(response, "status", None) == 206
            mode = "ab" if resume_accepted else "wb"
            completed = existing if resume_accepted else 0
            next_report = completed + 256 * 1024 * 1024
            started = time.monotonic()
            with response, temporary.open(mode) as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)
                    completed += len(block)
                    if completed >= next_report:
                        elapsed = max(time.monotonic() - started, 1e-6)
                        rate = (completed - (existing if resume_accepted else 0)) / elapsed / 1e6
                        print(
                            f"    {completed / 1e9:.2f}/{item['size'] / 1e9:.2f} GB "
                            f"({100 * completed / item['size']:.1f}%, {rate:.1f} MB/s)",
                            flush=True,
                        )
                        next_report += 256 * 1024 * 1024
            if digest(temporary, algorithm) != expected:
                raise ValueError(f"Checksum mismatch for {filename}")
            temporary.replace(target)
        manifest.append({
            "filename": filename,
            "bytes": item["size"],
            "checksum": item["checksum"],
            "status": status,
        })
        print(f"[{index}/{len(selected)}] {filename}: {status}", flush=True)

    lines = ["filename,bytes,checksum,status"]
    lines.extend(
        f'"{row["filename"]}",{row["bytes"]},"{row["checksum"]}",{row["status"]}' for row in manifest
    )
    (args.destination / "download_manifest.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Verified {len(manifest)} files in {args.destination}")


if __name__ == "__main__":
    main()
