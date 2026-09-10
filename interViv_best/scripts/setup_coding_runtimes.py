"""Prepare a verified local Piston package mirror, or install its four runtimes.

Downloads happen only with --download. The application never downloads runtimes.
Piston's own installer checks the upstream SHA-256 again inside Docker.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

PACKAGES = {"python": "3.12.0", "node": "20.11.1", "java": "15.0.2", "gcc": "10.2.0"}
INDEX = "https://github.com/engineer-man/piston/releases/download/pkgs/index"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", type=Path, help="Explicitly download the approved runtimes into this cache directory")
    parser.add_argument("--install", action="store_true", help="Install through Piston's localhost API")
    args = parser.parse_args()
    if args.download:
        destination = args.download.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-fsSL", "--retry", "3", "--max-time", "90", INDEX,
                        "-o", str(destination / "upstream-index")], check=True)
        entries = list(csv.reader((destination / "upstream-index").read_text().splitlines()))
        mirror = []
        for language, version in PACKAGES.items():
            row = next(r for r in entries if r[:2] == [language, version])
            _, _, checksum, url = row
            if not url.startswith("https://github.com/engineer-man/piston/releases/download/"):
                raise ValueError("Unexpected upstream package URL")
            filename = f"{language}-{version}.tar.gz"
            archive = destination / filename
            if not archive.exists() or hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != checksum:
                print(f"Downloading {language} {version}", flush=True)
                subprocess.run(["curl", "-fsSL", "--retry", "3", "--max-time", "300", url,
                                "-o", str(archive)], check=True)
            with archive.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != checksum:
                raise ValueError(f"Checksum mismatch for {filename}; do not install")
            mirror.append(f"{language},{version},{checksum},http://runtime-cache/{filename}")
            print(f"Verified {filename}: {checksum}", flush=True)
        (destination / "index").write_text("\n".join(mirror) + "\n")
        print("Mirror ready. Set CODING_RUNTIME_CACHE to this directory when starting compose.")
    if args.install:
        for language, version in PACKAGES.items():
            print(f"Installing {language} {version} through local Piston", flush=True)
            request = Request("http://127.0.0.1:19000/api/v2/packages",
                              data=json.dumps({"language": language, "version": version}).encode(),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=240) as response:
                print(response.read(8192).decode(), flush=True)
    if not args.download and not args.install:
        parser.error("Choose --download DIRECTORY or --install")


if __name__ == "__main__":
    main()
