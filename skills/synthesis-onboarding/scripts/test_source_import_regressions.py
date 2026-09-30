"""Actual source-loader boundaries after verified private in-process activation."""

import json
import py_compile
import subprocess
import sys

import pytest

import release_runtime as runtime
from test_release_runtime import active as _active, replace, write_receipt

active = _active


@pytest.mark.parametrize("receipt", [False, True])
@pytest.mark.parametrize("loads", [1, 4])
def test_verified_private_consumer_refuses_sourceless_release(active, receipt, loads):
    pointer, root, data = active
    helper = root / "source_only.py"
    helper.write_text("VALUE = 'cached'\n")
    py_compile.compile(str(helper), cfile=str(root / "source_only.pyc"), doraise=True)
    helper.rename(root / "source_only.retained")
    data = replace(pointer, data, content_digest=runtime.tree_digest(root))
    if receipt:
        write_receipt(pointer, root, data)
    # Real verified_release API, then an ordinary import exactly as a private
    # in-process consumer uses it. No source-contract injection in this child.
    code = """import sys,types
p, pointer, count = sys.argv[1:]
m=types.ModuleType('verified_owner');m.__file__=p
exec(compile(open(p,'rb').read(),p,'exec'),m.__dict__)
for _ in range(int(count)): active=m.verified_release(pointer)
sys.path.insert(0,active['release_root'])
import source_only
print(source_only.VALUE)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-c",
            code,
            runtime.__file__,
            str(pointer),
            str(loads),
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert b"requires Python source" in result.stderr
    assert b"cached" not in result.stdout


def test_repeated_contract_activation_retains_prior_roots_without_recursion(tmp_path):
    first, second, external = [
        tmp_path / value for value in ("first", "second", "external")
    ]
    for path in (first, second, external):
        path.mkdir()
    source = external / "external.py"
    source.write_text("VALUE = 'external'\n")
    bytecode = external / "external.pyc"
    py_compile.compile(str(source), cfile=str(bytecode), doraise=True)
    (first / "alias.py").symlink_to(source)
    owned = first / "owned.pyc"
    owned.write_bytes(bytecode.read_bytes())
    code = (
        runtime.SOURCE_IMPORT_CONTRACT
        + """
import importlib.machinery, json
first,second,external=_source_sys.argv[1:]
enable_source_imports(first)
source_loader=_source_loaders.SourceFileLoader.get_code
bytecode_loader=_source_loaders.SourcelessFileLoader.get_code
for _ in range(4096):
    enable_source_imports(first)
    enable_source_imports(second)
assert source_loader is _source_loaders.SourceFileLoader.get_code
assert bytecode_loader is _source_loaders.SourcelessFileLoader.get_code
for path,loader,error in [
    (first+'/owned.pyc',importlib.machinery.SourcelessFileLoader,'requires Python source'),
    (first+'/alias.py',importlib.machinery.SourceFileLoader,'symbolic link'),
]:
    try: loader('fixture',path).get_code('fixture')
    except ImportError as exc: assert error in str(exc)
    else: raise AssertionError('protected prior root executed')
namespace={}
exec(importlib.machinery.SourcelessFileLoader('external',external+'/external.pyc').get_code('external'),namespace)
assert namespace['VALUE']=='external'
print(json.dumps({'activations':8193,'prior_roots_protected':True,'external_bytecode_unchanged':True}))
"""
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            "-c",
            code,
            str(first),
            str(second),
            str(external),
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["activations"] == 8193
