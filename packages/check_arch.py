#!/usr/bin/env python3
"""Prepare a candidate recipe for actual makepkg acceptance, without publishing."""
import argparse
from pathlib import Path
import shutil
import subprocess

from build import build_package, make_archive, write_adapters

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
commit = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
args.output.mkdir(parents=True, exist_ok=False)
package = build_package(args.source, args.output / "package", commit=commit)
archive = make_archive(package, args.output / "candidate.tar.gz")
metadata = write_adapters(package, archive, args.output / "adapters")
recipe = args.output / "adapters/aur"
shutil.copyfile(archive, recipe / ("synthesis-" + metadata["version"] + ".tar.gz"))
path = recipe / "PKGBUILD"
source = path.read_text()
# Only acquisition differs: CI verifies identical candidate archive bytes from
# its build output before the release URL exists. Checksums remain unchanged.
source = source.replace('source=("synthesis-${pkgver}.tar.gz::' + metadata["url"] + '")',
                        'source=("synthesis-${pkgver}.tar.gz")')
path.write_text(source)
print(recipe)
