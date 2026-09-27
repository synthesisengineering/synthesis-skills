import subprocess
import pytest
import publication_command as shell


def test_ansi_c_escaped_apostrophe_and_literal_substitution():
    result = shell.parse_shell(r"printf %s $'it\'s\n$(never)`never`'")
    assert result.commands == [["printf", "%s", "it's\n$(never)`never`"]]
    assert result.nested == [] and not result.dynamic


def test_literal_previous_assignment_redirection():
    result = shell.parse_shell(
        'P=/tmp/example; printf text > "$P"', resolve_literals=True
    )
    assert result.redirections == [(1, ">", "/tmp/example")]
    assert not result.dynamic


@pytest.mark.parametrize(
    "command",
    [
        'printf text > "$P"',
        'P=/tmp/a printf text > "$P"',
        'P=$(printf /tmp/a); printf text > "$P"',
        'P=/tmp/a; read P; printf text > "$P"',
        'P=/tmp/a; while read P; do printf text > "$P"; done',
        'P=/tmp/a || P=/tmp/b; printf text > "$P"',
        'P=/tmp/a & printf text > "$P"',
    ],
)
def test_unresolved_or_flow_dependent_variables_stay_dynamic(command):
    result = shell.parse_shell(command, resolve_literals=True)
    assert result.dynamic and any(
        "$P" in operand for _, _, operand in result.redirections
    )


def test_single_quoted_variable_stays_literal():
    result = shell.parse_shell("P=/tmp/a; printf text > '$P'", resolve_literals=True)
    assert result.redirections == [(1, ">", "$P")]


def test_variable_value_quoting():
    result = shell.parse_shell(
        'P="/tmp/a b"; printf text > "$P"', resolve_literals=True
    )
    assert result.redirections == [(1, ">", "/tmp/a b")]
    unresolved = shell.parse_shell(
        'P="/tmp/a b"; printf text > $P', resolve_literals=True
    )
    assert unresolved.dynamic


def test_ansi_in_nested_command_is_balanced():
    result = shell.parse_shell(r"printf \"$(printf %s $'a\'b)')\"")
    assert result.nested == [r"printf %s $'a\'b)'"]


@pytest.mark.parametrize(
    "command",
    [
        "'P'=/tmp/a; printf text > \"$P\"",
        'P\\=/tmp/a; printf text > "$P"',
        'P=/tmp/old; P=/tmp/new Q=$P; printf text > "$Q"',
        'P=~/scratch; printf text > "$P"',
        "IFS=/; P=/tmp/a; printf text > $P",
    ],
)
def test_literal_resolution_requires_actual_assignment_grammar(command):
    result = shell.parse_shell(command, resolve_literals=True)
    assert result.dynamic
    assert any("$" in operand for _, _, operand in result.redirections)


def test_ansi_subset_matches_actual_zsh_literal_bytes():
    import subprocess

    command = r"printf '%s' $'it\'s\n$(inert)`inert`\\end'"
    parsed = shell.parse_shell(command)
    actual = subprocess.run(
        ["/bin/zsh", "-fc", command], capture_output=True, timeout=5, check=True
    )
    assert actual.stdout == parsed.commands[0][-1].encode()
    assert not parsed.nested and not parsed.dynamic


@pytest.mark.parametrize("word", [r"$'\x00'", r"$'\cA'", "$'unterminated"])
def test_unsupported_ansi_escapes_fail_closed(word):
    with pytest.raises(ValueError):
        shell.parse_shell("printf %s " + word)


# Independent adversarial review controls.
def test_tied_zsh_parameters_are_not_ordinary_literals(tmp_path):
    safe = tmp_path / "safe"
    protected = tmp_path / "protected"
    safe.mkdir()
    protected.mkdir()
    command = f'PATH={safe}; path={protected}; printf "%s" "$PATH/file"'
    actual = subprocess.run(
        ["/bin/zsh", "-fc", command], capture_output=True, timeout=5, check=True
    ).stdout.decode()
    assert actual == str(protected / "file")
    parsed = shell.parse_shell(
        command.replace('printf "%s"', "printf x >"), resolve_literals=True
    )
    assert parsed.dynamic, parsed
    assert "$PATH" in parsed.redirections[0][2]


@pytest.mark.parametrize(
    "name",
    [
        "PATH",
        "path",
        "FPATH",
        "fpath",
        "CDPATH",
        "cdpath",
        "MANPATH",
        "manpath",
        "RANDOM",
        "SECONDS",
        "LINENO",
        "SHELLOPTS",
        "IFS",
        "BASH_ENV",
        "ENV",
    ],
)
def test_shell_state_assignments_cannot_grant_literal_authority(name):
    parsed = shell.parse_shell(
        f'{name}=/safe; P=/elsewhere; printf x > "$P"', resolve_literals=True
    )
    assert parsed.dynamic and "$P" in parsed.redirections[0][2]


@pytest.mark.parametrize(
    "command",
    [
        'P=/safe; read P; printf x > "$P"',
        'P=/safe || P=/else; printf x > "$P"',
        'P=/safe; ( P=/else ); printf x > "$P"',
        'P=/safe; export P=/else; printf x > "$P"',
        'P=$(printf /safe); printf x > "$P"',
    ],
)
def test_ambiguous_flow_never_claims_literal_destination(command):
    parsed = shell.parse_shell(command, resolve_literals=True)
    assert parsed.dynamic


@pytest.mark.parametrize(
    "word",
    [
        r"$'it\'s\nend'",
        r"$'back\\slash\ttab'",
        r"$'$(literal)`literal`'",
        "$'prefix'\" suffix\"",
        r"$'\a\b\e\f\r\v'",
    ],
)
def test_actual_zsh_literal_bytes(word):
    command = "printf '%s' " + word
    actual = subprocess.run(
        ["/bin/zsh", "-fc", command], capture_output=True, check=True, timeout=5
    )
    assert actual.stdout == shell.parse_shell(command).commands[0][-1].encode()


def test_ansi_publication_is_still_publication():
    assert shell.inspect_command("$'git' push origin HEAD").publication


@pytest.mark.parametrize(
    "upper,lower",
    [
        ("PATH", "path"),
        ("PROMPT", "prompt"),
        ("FPATH", "fpath"),
        ("CDPATH", "cdpath"),
        ("MANPATH", "manpath"),
    ],
)
def test_actual_zsh_tied_parameter_pairs_remain_unresolved(upper, lower):
    command = f'{upper}=/tmp/safe; {lower}=/tmp/protected; printf "%s" "${upper}/file"'
    actual = subprocess.run(
        ["/bin/zsh", "-fc", command], capture_output=True, timeout=5, check=True
    )
    assert actual.stdout == b"/tmp/protected/file"
    parsed = shell.parse_shell(
        command.replace('printf "%s"', "printf x >"), resolve_literals=True
    )
    assert parsed.dynamic and "$" + upper in parsed.redirections[0][2]


def test_resolver_does_not_classify_native_zsh_special_parameters_as_scalars():
    import re

    actual = subprocess.run(
        ["/bin/zsh", "-fc", "print -rl -- ${(ok)parameters[(R)*special*]}"],
        capture_output=True,
        timeout=5,
        check=True,
    )
    names = [
        name
        for name in actual.stdout.decode().splitlines()
        if re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", name)
    ]
    assert "PATH" in names and "prompt" in names
    for name in names:
        parsed = shell.parse_shell(
            f'{name}=/tmp/safe; P=/tmp/ordinary; printf x > "$P"', resolve_literals=True
        )
        assert parsed.dynamic and "$P" in parsed.redirections[0][2], name
