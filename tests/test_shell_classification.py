"""R3.2 / R8.2: the Bash guard tells a command that runs from words that are only data.

A deploy is caught directly, behind wrappers (env, nice, timeout, command, exec, ...), inside
`bash -c`, `$(...)`, backticks, an unquoted heredoc, eval, or a shell reading its stdin. The same
words quoted, in a quoted-tag heredoc, or as arguments to echo or grep are data. Text that cannot
be read (unbalanced quotes, nesting too deep) is judged on its raw words, and an unreadable
command with no deploy word in it is never blocked. Cases carried from the old
publication_command and publish_guard shell tests.
"""

import shlex
import statistics
import subprocess
import time

import pytest

from synthesis import guards

DEPLOY = "wrangler pages deploy dist"


@pytest.fixture
def where(tmp_path):
    """A plain directory to run from, and a site repository that deploys on push."""
    site = tmp_path / "site"
    subprocess.run(["git", "init", "-q", "-b", "main", str(site)], check=True)
    (site / "README.md").write_text("site\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(site), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(site), "commit", "-qm", "first"], check=True)
    (tmp_path / "elsewhere").mkdir()
    return tmp_path / "elsewhere", site


def _check(command, where, cwd=None):
    elsewhere, site = where
    config = {"push_deploys": [str(site)], "deploy_patterns": [r"release-gate\.mjs\s+deploy"]}
    return guards.check("Bash", {"command": command.replace("{site}", str(site))}, config, cwd=str(cwd or elsewhere))


RUNS = [
    DEPLOY, f"/usr/local/bin/{DEPLOY}", f"env FOO=1 {DEPLOY}", f"env -i {DEPLOY}", f"env -u HOME {DEPLOY}",
    f"nice {DEPLOY}", f"nice -n 10 {DEPLOY}", f"timeout 60 {DEPLOY}", f"timeout -s KILL 5m {DEPLOY}",
    f"command {DEPLOY}", f"exec {DEPLOY}", f"exec -a name {DEPLOY}", f"nohup {DEPLOY} &", f"time {DEPLOY}",
    f"sudo -u me {DEPLOY}", f"echo dist | xargs {DEPLOY}", f"npx --yes {DEPLOY}", f"FOO=1 BAR=2 {DEPLOY}",
    f"bash -c '{DEPLOY}'", f'sh -c "cd /tmp && {DEPLOY}"', f"zsh -lc '{DEPLOY}'", f"bash -e -c '{DEPLOY}'",
    f"echo $({DEPLOY})", f"out=$({DEPLOY})", f"printf '%s' \"$({DEPLOY})\"", f"echo `{DEPLOY}`",
    f"cat <<EOF\n$({DEPLOY})\nEOF", f"cat <<EOF\n`{DEPLOY}`\nEOF", f"cat <<-EOF\n\t$({DEPLOY})\n\tEOF",
    f"bash <<'EOF'\n{DEPLOY}\nEOF", f"bash <<< '{DEPLOY}'", f"printf '{DEPLOY}\\n' | sh",
    f"cat <<'S' | bash\n{DEPLOY}\nS", f". /dev/stdin <<'S'\n{DEPLOY}\nS", f"bash /dev/stdin <<'S'\n{DEPLOY}\nS",
    f"printf '{DEPLOY}\\n' | source /dev/stdin", f"eval '{DEPLOY}'", f"env -S '{DEPLOY}'",
    f"if true; then {DEPLOY}; fi", f"{{ {DEPLOY}; }}", f"(cd /tmp && {DEPLOY})", f"ls && {DEPLOY}",
    f"ls\n{DEPLOY}", "bash -c 'wr\"\"angler pages deploy dist'", "printf '%s' \"$(wr''angler pages deploy dist)\"",
    "python3 -m twine upload dist/*", "node release-gate.mjs deploy-pages", f"{DEPLOY} 2>&1 | tail -3",
    f"echo $(echo $({DEPLOY}))", f"x=\"$(cat <<'EOF'\nit's here\nEOF\n)\"; {DEPLOY}",
]


@pytest.mark.parametrize("command", RUNS)
def test_a_deploy_that_runs_is_caught_however_it_is_wrapped(where, command):
    reason = _check(command, where)
    assert reason and "approve" in reason, command


DATA = [
    f"echo '{DEPLOY}'", f"echo {DEPLOY}", f"grep -n '{DEPLOY}' notes.md", f"grep {DEPLOY}", "rg 'wrangler.pages.deploy' -n",
    f"git commit -m '{DEPLOY}'", f"git commit -m \"run {DEPLOY} later\"", f"printf '%s' '|' {DEPLOY}",
    f"echo \"{DEPLOY}\" >> notes.md", f"cat <<'EOF'\n$({DEPLOY})\nEOF", f"cat <<\\EOF\n{DEPLOY}\nEOF",
    f"cat <<\"EOF\"\n`{DEPLOY}`\nEOF", f"cat <<EOF > notes.md\n{DEPLOY}\nEOF", f"cat <<EOF\n\\$({DEPLOY})\nEOF",
    f"python3 - <<'PY'\nprint('{DEPLOY}')\nPY", f"printf 'safe' # ; {DEPLOY}", "command -v wrangler",
    f"bash -c 'printf safe' <<'DATA'\n{DEPLOY}\nDATA", f"eval <<'DATA'\n{DEPLOY}\nDATA", "env -S 'printf %s deployment'",
    f"bash <<< 'printf \"%s\" \"{DEPLOY}\"'", f"bash scripts/build.sh <<'DATA'\n{DEPLOY}\nDATA",
    f"git log --grep='{DEPLOY}' --oneline | head -2", f"printf '%s' $'it\\'s {DEPLOY}'",
    f"git commit -m \"$(cat <<'EOF'\nDon't {DEPLOY} yet\nEOF\n)\"", "echo 'release-gate.mjs deploy-pages'",
]


@pytest.mark.parametrize("command", DATA)
def test_the_same_words_as_data_are_never_a_deploy(where, command):
    assert _check(command, where) is None, command


PUSHES = ["env GIT_TRACE=0 git -C {site} push", "command git -C {site} push", "timeout 30 git -C {site} push",
          "nice git -C {site} push", "bash -c 'git -C {site} push'", "x=$(git -C {site} push 2>&1)",
          "if true; then git -C {site} push origin main; fi", "printf 'git -C {site} push\\n' | sh",
          "for r in a b; do git -C $r push; done", "cd $SITE_DIR && git push",
          "cd {site} && $'git' push origin HEAD", "cd {site} && $'g\\x69t' $'p\\165sh' origin HEAD",
          "git -C {site} $'push'"]


@pytest.mark.parametrize("command", PUSHES)
def test_a_push_into_a_site_or_into_a_repository_named_by_a_variable_is_a_deploy(where, command):
    assert "approve" in _check(command, where), command


@pytest.mark.parametrize("command", ["git commit -m 'git -C {site} push'", "echo git -C {site} push",
                                     "git -C {site} log --grep='push'", "git -C {site} status && echo push"])
def test_push_words_as_data_are_not_a_deploy(where, command):
    assert _check(command, where) is None, command


@pytest.mark.parametrize("command", ["ls '", 'echo "unterminated', "cat <<", "grep -n 'x notes.md && ls",
                                     "diff <(sort a) <(sort b"])
def test_an_unreadable_command_with_no_deploy_word_is_never_blocked(where, command):
    assert _check(command, where) is None, command


@pytest.mark.parametrize("command", [f"{DEPLOY} '", f"echo \"{DEPLOY}", "git -C {site} push origin main '"])
def test_an_unreadable_command_with_a_deploy_word_is_judged_on_its_raw_words(where, command):
    assert "approve" in _check(command, where), command


def test_nesting_past_the_bound_is_judged_on_raw_words(where):
    deep, plain = DEPLOY, "echo hello"
    for _ in range(guards.MAX_DEPTH + 2):
        deep, plain = f"bash -c {shlex.quote(deep)}", f"bash -c {shlex.quote(plain)}"
    assert "approve" in _check(deep, where)
    assert _check(plain, where) is None


@pytest.mark.parametrize("command,blocked", [("echo 'rm -rf ~'", False), ("bash -c 'rm -rf ~'", True),
                                             ("sudo rm -rf /", True), ("x=$(rm -rf ~)", True),
                                             ("git push origin +main", True), ("git push origin +feature", False),
                                             ("grep -r 'rm -rf ~' .", False)])
def test_destructive_commands_follow_the_same_reading(where, command, blocked):
    assert (_check(command, where) is not None) is blocked, command


def test_reading_a_long_command_stays_fast(where):
    elsewhere, _ = where
    commands = [c.replace("{site}", "x") for c in RUNS + DATA + PUSHES] + ["cat <<'EOF' > f.md\n" + "line of text\n" * 2000 + "EOF"]
    times = []
    for command in commands:
        start = time.perf_counter()
        guards._parse(command, str(elsewhere))
        times.append(time.perf_counter() - start)
    assert statistics.median(times) < 0.002 and max(times) < 0.03


# The project-state helper's comparison with publication_command's tests (2026-10-05), as named cases.
@pytest.mark.parametrize("command,blocked", [
    ("cd {site} && $'git' push origin HEAD", True),                    # (1) ANSI-C quoting hides nothing
    ("echo wrangler pages deploy", False),                              # (2) arguments are data
    ("grep 'wrangler pages deploy' x", False),
    ("cat <<EOF\n$(wrangler pages deploy dist)\nEOF", True),          # (3) an unquoted heredoc runs $(...)
    ("cat <<'EOF'\n$(wrangler pages deploy dist)\nEOF", False),
    ("wrangler pages deploy dist '", True),                             # (4) unbalanced: raw words
    ("ls -la '", False),
    ("timeout 120 wrangler pages deploy dist", True),                   # (4) behind timeout
    ("timeout --signal=KILL 2m wrangler pages deploy dist", True),
])
def test_the_cases_found_by_comparing_with_the_old_shell_tests(where, command, blocked):
    assert (_check(command, where) is not None) is blocked, command
