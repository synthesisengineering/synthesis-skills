#!/usr/bin/env python3
"""Build inert channel packages from one reviewed tagged release; never publish."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
REPOSITORY = "https://github.com/synthesisengineering/synthesis-skills"


def source_digest(source, commit):
    """Bind packages to the exact materialized Git release, excluding build debris."""
    spec = importlib.util.spec_from_file_location("package_build_runtime", HERE.parent / "skills/synthesis-onboarding/scripts/release_runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    if not (source / ".git").exists():
        # Nongit trees are supported by disposable builder fixtures. The public
        # CLI separately requires a clean repository at its exact version tag.
        return runtime.tree_digest(source)
    archive = subprocess.check_output(["git", "-C", str(source), "archive", "--format=tar", commit])
    with tempfile.TemporaryDirectory(prefix="synthesis-package-source-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive)) as packed:
            packed.extractall(directory, filter="data")
        return runtime.tree_digest(directory)


def build_package(source, destination, *, commit):
    source, destination = Path(source), Path(destination)
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "onboard.sh", "LICENSE-APACHE"):
        path = source / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("package source must contain regular release files")
    versions = [json.loads((source / ("." + client + "-plugin/plugin.json")).read_text())["version"] for client in ("claude", "codex")]
    if len(set(versions)) != 1 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", versions[0]):
        raise ValueError("release manifests must agree on an exact version")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("package requires an exact source commit")
    version = versions[0]
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "bin").mkdir()
    (destination / "lib").mkdir()
    shutil.copyfile(HERE / "launcher.sh", destination / "bin/synthesis")
    (destination / "bin/synthesis").chmod(0o755)
    shutil.copyfile(HERE / "package_launcher.py", destination / "lib/package_launcher.py")
    shutil.copyfile(HERE.parent / "skills/synthesis-onboarding/scripts/release_runtime.py", destination / "lib/release_runtime.py")
    shutil.copyfile(source / "onboard.sh", destination / "lib/onboard.sh")
    shutil.copyfile(source / "LICENSE-APACHE", destination / "LICENSE")
    metadata = {"schema_version": 1, "version": version, "commit": commit,
                "source_url": REPOSITORY, "source_content_digest": source_digest(source, commit),
                "bootstrap_sha256": hashlib.sha256((source / "onboard.sh").read_bytes()).hexdigest()}
    (destination / "lib/release.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (destination / "package.json").write_text(json.dumps({
        "name": "@synthesiswork/synthesis", "version": version,
        "description": "Verified Synthesis installation and lifecycle command",
        "license": "Apache-2.0", "bin": {"synthesis": "bin/synthesis"},
        "files": ["bin/", "lib/", "README.md", "LICENSE"],
        "os": ["darwin", "linux"], "repository": {"type": "git", "url": "git+" + REPOSITORY + ".git"},
        "homepage": "https://synthesiswork.org/download/", "publishConfig": {"access": "public"},
    }, indent=2) + "\n")
    (destination / "README.md").write_text(
        "# Synthesis\n\nThis package installs the Synthesis command. It does not activate skills, hooks or services.\n\n"
        "Requirements: Git and Python 3.12, 3.13 or 3.14. Homebrew declares these dependencies.\n\n"
        "Standalone `stage-core --for-tool TOOL --no-dormant-core` needs only Python 3.9+; "
        "it reports the declined choice without acquisition or state writes.\n\n"
        "Run `synthesis setup --profile full` or `synthesis setup --profile skills-only`. "
        "For an individual skill, use `synthesis setup --profile modular --skill NAME`; "
        "add `--no-dormant-core` to omit optional core staging.\n\n"
        "The package verifies its bootstrap and acquires its exact source commit. The shared lifecycle engine "
        "verifies release provenance before activation. `synthesis doctor` reports each lifecycle layer. "
        "Updates and service activation require explicit commands. No telemetry.\n")
    return destination


def make_archive(package, path):
    package, path = Path(package), Path(path)
    with path.open("xb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for item in sorted(package.rglob("*")):
                if item.is_symlink() or not (item.is_file() or item.is_dir()):
                    raise ValueError("package contains unsupported object")
                info = archive.gettarinfo(str(item), "synthesis/" + item.relative_to(package).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o755 if item.is_dir() or item.stat().st_mode & 0o111 else 0o644
                if item.is_file():
                    with item.open("rb") as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)
    return path


def write_adapters(package, archive, destination):
    metadata = json.loads((Path(package) / "lib/release.json").read_text())
    version = metadata["version"]
    checksum = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    url = REPOSITORY + "/releases/download/v%s/synthesis-%s.tar.gz" % (version, version)
    dest = Path(destination)
    (dest / "Formula").mkdir(parents=True, exist_ok=False)
    (dest / "aur").mkdir()
    (dest / "Formula/synthesis.rb").write_text('''class Synthesis < Formula
  desc "Verified installation and lifecycle for the Synthesis ecosystem"
  homepage "https://synthesiswork.org/download/"
  url "%s"
  sha256 "%s"
  license "Apache-2.0"
  depends_on "git"
  depends_on "python@3.12"
  def install
    libexec.install Dir["*"]
    (bin/"synthesis").write_env_script libexec/"bin/synthesis",
      SYNTHESIS_BOOTSTRAP_PYTHON: Formula["python@3.12"].opt_bin/"python3.12"
  end
  test do
    assert_match "%s", shell_output("#{bin}/synthesis --version")
    assert_match "--profile", shell_output("#{bin}/synthesis --help")
  end
end
''' % (url, checksum, version))
    (dest / "aur/PKGBUILD").write_text('''pkgname=synthesis
pkgver=%s
pkgrel=1
pkgdesc='Verified installation and lifecycle for the Synthesis ecosystem'
arch=('any')
url='https://synthesiswork.org/download/'
license=('Apache-2.0')
depends=('git' 'python>=3.12' 'python<3.15')
source=("synthesis-${pkgver}.tar.gz::%s")
sha256sums=('%s')
package() {
  install -dm755 "$pkgdir/usr/lib/synthesis" "$pkgdir/usr/bin"
  cp -a "$srcdir/synthesis/". "$pkgdir/usr/lib/synthesis/"
  ln -s /usr/lib/synthesis/bin/synthesis "$pkgdir/usr/bin/synthesis"
  install -Dm644 "$srcdir/synthesis/LICENSE" "$pkgdir/usr/share/licenses/synthesis/LICENSE"
}
''' % (version, url, checksum))
    metadata.update(archive=Path(archive).name, sha256=checksum, url=url,
                    npm_package="@synthesiswork/synthesis", brew_formula="synthesisengineering/tap/synthesis",
                    prepared_unpublished={"aur_package": "synthesis"})
    (dest / "distribution.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=HERE.parent)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if root != HERE.parent:
        raise SystemExit("run the builder from the exact release being packaged")
    git = lambda *parts: subprocess.check_output(["git", "-C", str(root), *parts], text=True).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise SystemExit("package source must be the repository root")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise SystemExit("package release source must be clean")
    version = json.loads((root / ".claude-plugin/plugin.json").read_text())["version"]
    commit = git("rev-parse", "HEAD^{commit}")
    if git("rev-parse", "v" + version + "^{commit}") != commit:
        raise SystemExit("package source must equal its exact version tag")
    args.output.mkdir(parents=True, exist_ok=False)
    package = build_package(root, args.output / "npm", commit=commit)
    archive = make_archive(package, args.output / ("synthesis-" + version + ".tar.gz"))
    print(json.dumps(write_adapters(package, archive, args.output / "adapters"), indent=2))


if __name__ == "__main__":
    main()
