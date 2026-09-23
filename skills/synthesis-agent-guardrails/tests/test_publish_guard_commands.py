"""Command/data distinction at the real approval gate; no command is executed."""
from pathlib import Path
import shlex

import pytest

from test_publish_guard_worktrees import real_repos, gated, pg


@pytest.fixture(scope="module", autouse=True)
def _parser_runtime():
    """Bind the same-repo shell parser eagerly (fails fast on layout drift)."""
    pg._ensure_shell_parser()
    assert pg.inspect_command is not None
    yield


@pytest.mark.parametrize("command", [
    "python3 - <<'PY'\nprint('deployment status')\nPY\n",
    "python3 - <<'PY'\nprint('git push origin main')\nPY\n",
    "cat <<'TEXT' | head -1\ngit push origin main\nTEXT\n",
    "cat <<\\TEXT\nwrangler pages deploy dist\nTEXT\n",
    "cat <<'TEXT'\n$(git push origin main)\nTEXT\n",
    "printf '%s\\n' 'git' 'push' | head -1",
    "printf '%s\\n' 'wrangler' 'pages' 'deploy'",
    "printf '%s' '|' git push",
    "git log --grep='git push' --oneline | head -2",
    "git commit -m 'notes on git push and deployment'",
    "rg -n 'git.push|deployment' notes.md | head -2",
    "printf '%s' 'release-gate.mjs' 'deploy-pages'",
    "printf '%s' 'deployment' ; printf '%s' 'push'",
    "printf '%s' 'safe' # git push origin main\n",
    "bash -c 'printf \"%s\" \"deployment status\"'",
    "printf '%s' 'deployment' > report.txt",
    "git commit-graph verify",
    "git multi-pack-index verify",
])
def test_literal_data_never_enters_publication_gate(real_repos, monkeypatch, command):
    # Deliberately unusable config proves classification does not consult a
    # publication authority store for a command outside that class.
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(real_repos['root'] / 'absent.json'))
    assert gated(monkeypatch, command, real_repos['canonical']) == 0
    assert not real_repos['state'].exists()


@pytest.mark.parametrize("command", [
    "git push origin HEAD:main",
    "printf safe ; git push origin HEAD:main",
    "cat <<'TEXT'\nliteral deployment status\nTEXT\ngit push origin HEAD:main",
    "bash <<'SCRIPT'\ngit push origin HEAD:main\nSCRIPT\n",
    "cat <<TEXT\n$(git push origin HEAD:main)\nTEXT\n",
    "cat <<TEXT\n`git push origin HEAD:main`\nTEXT\n",
    "printf '%s' \"$(git push origin HEAD:main)\"",
    "printf '%s' `git push origin HEAD:main`",
    "bash -c 'git push origin HEAD:main'",
    "sh -c 'wrangler pages deploy dist'",
    "env git push origin HEAD:main",
    "command git push origin HEAD:main",
    "npx wrangler pages deploy dist",
    "node release-gate.mjs deploy-pages fake missing.json",
    "if true; then git push origin HEAD:main; fi",
    "git push origin HEAD:main '",
])
def test_executable_publication_remains_guarded(real_repos, monkeypatch, command):
    assert gated(monkeypatch, command, real_repos['canonical']) == 2
    assert not Path(pg.ledger_path()).exists()


@pytest.mark.parametrize("flag", ['--quiet', '--verbose', '--porcelain', '--set-upstream', '-u', '--atomic'])
def test_non_target_changing_flags_preserve_exact_approval(real_repos, monkeypatch, flag):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic one-ref approval') == 0
    command = f'cd {shlex.quote(str(repo))} && git push {flag} origin HEAD:main'
    assert gated(monkeypatch, command, real_repos['root']) == 0
    assert not Path(pg.ledger_path()).exists()
    assert gated(monkeypatch, command, real_repos['root']) == 2


def test_unprotected_flagged_push_in_compound_command_is_not_a_site_publish(real_repos, monkeypatch):
    repo = real_repos['unrelated']
    command = f'cd {shlex.quote(str(repo))} && git push -u origin HEAD:topic && git status --short'
    assert gated(monkeypatch, command, real_repos['canonical']) == 0


def test_dry_run_does_not_consume_publication_approval(real_repos, monkeypatch):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic preserved approval') == 0
    before = Path(pg.ledger_path()).read_bytes()
    assert gated(monkeypatch, 'git push --dry-run origin HEAD:main', repo) == 0
    assert Path(pg.ledger_path()).read_bytes() == before


@pytest.mark.parametrize('flag', ['--force', '--delete', '--mirror', '--all', '--force-with-lease', '--dry-run=false'])
def test_target_or_authority_changing_flags_are_not_reclassified_as_harmless(real_repos, monkeypatch, flag):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic preserved approval') == 0
    before = Path(pg.ledger_path()).read_bytes()
    assert gated(monkeypatch, f'git push {flag} origin HEAD:main', repo) == 2
    assert Path(pg.ledger_path()).read_bytes() == before


@pytest.mark.parametrize('command', [
    'nice -n 5 git push origin HEAD:main',
    'env -P /usr/bin git push origin HEAD:main',
    'time -o timing.txt git push origin HEAD:main',
    'xargs -n 1 git push origin HEAD:main',
    'env -S "git push origin HEAD:main"',
    'env "-Sgit push origin HEAD:main"',
    'env -S "FLAG=1 git push origin HEAD:main"',
    'env bash --command "git push origin HEAD:main"',
    'zsh --command "git push origin HEAD:main"',
    "bash -c 'g\"\"it p\"\"ush origin HEAD:main'",
    "printf 'git push origin HEAD:main\\n' | sh",
    "cat <<'SCRIPT' | sh\ngit push origin HEAD:main\nSCRIPT\n",
    "printf 'git push origin HEAD:main\\n' | source /dev/stdin",
    ". /dev/stdin <<'SCRIPT'\ngit push origin HEAD:main\nSCRIPT\n",
    'npx --yes --package=wrangler wrangler pages deploy dist',
    'npx --call="git push origin HEAD:main"',
    'npm exec -- wrangler pages deploy dist',
    'node --no-warnings fixture-release-gate.mjs deploy-worker fake missing.json',
    "printf '%s' \"$(g''it p''ush origin HEAD:main)\"",
    'echo "$(case x in x) git push origin HEAD:main ;; esac)"',
    'git -c repositories.fixture=. for-each-repo --config=repositories.fixture push origin HEAD:main',
    'git submodule foreach "git push origin HEAD:main"',
])
def test_adversarial_execution_routes_never_skip_approval(real_repos, monkeypatch, command):
    assert gated(monkeypatch, command, real_repos['canonical']) == 2
    assert not real_repos['state'].exists()


def test_ordinary_unprotected_push_allows_output_filter_and_status(real_repos, monkeypatch):
    command = 'git push -q origin HEAD 2>&1 | tail -5; echo "git push status"'
    assert gated(monkeypatch, command, real_repos['unrelated']) == 0
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('separator', [';', '\n', '|', '||', '&'])
def test_complex_command_never_guesses_after_conditional_directory_change(real_repos, monkeypatch, separator):
    command = f'cd {shlex.quote(str(real_repos["unrelated"]))} {separator} git push -q origin HEAD 2>&1 | tail -5'
    assert gated(monkeypatch, command, real_repos['canonical']) == 2


def test_protected_complex_push_does_not_consume_exact_approval(real_repos, monkeypatch):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic preserved approval') == 0
    before = Path(pg.ledger_path()).read_bytes()
    assert gated(monkeypatch, 'git push -q origin HEAD:main 2>&1 | tail -5; echo done', repo) == 2
    assert Path(pg.ledger_path()).read_bytes() == before


@pytest.mark.parametrize('prefix', ['', 'printf "%s" "literal status" && ', 'printf "%s" "GIT_DIR=fake"; '])
def test_literal_directory_then_unprotected_filtered_push_is_resolved(real_repos, monkeypatch, prefix):
    command = prefix + f'cd {shlex.quote(str(real_repos["unrelated"]))} && git push -q origin HEAD 2>&1 | tail -5; echo done'
    assert gated(monkeypatch, command, real_repos['canonical']) == 0


@pytest.mark.parametrize('command', [
    "cat <<TEXT\n\\$(git push origin HEAD:main)\nTEXT\n",
    "bash <<'SCRIPT'\nprintf '%s' 'git push origin HEAD:main'\nSCRIPT\n",
    "bash <<< 'printf \"%s\" \"deployment status\"'",
    "command -v git push",
    "env -S 'printf %s deployment'",
    "bash -c 'printf safe' <<'DATA'\ngit push origin HEAD:main\nDATA\n",
    "eval <<'DATA'\ngit push origin HEAD:main\nDATA\n",
])
def test_shell_and_wrapper_literal_data_remains_harmless(real_repos, monkeypatch, command):
    monkeypatch.setenv('PUBLISH_GUARD_CONFIG', str(real_repos['root'] / 'absent.json'))
    assert gated(monkeypatch, command, real_repos['canonical']) == 0


def test_nested_substitution_inside_quotes_remains_execution(real_repos, monkeypatch):
    command = 'printf "%s" "$(printf "%s" "$(git push origin HEAD:main)")"'
    assert gated(monkeypatch, command, real_repos['canonical']) == 2


@pytest.mark.parametrize('prefix', ['builtin cd', 'command cd', 'pushd', 'chdir', 'source', '.'])
def test_parent_shell_mutators_cannot_select_ambient_unprotected_identity(real_repos, monkeypatch, prefix):
    command = f'{prefix} {shlex.quote(str(real_repos["canonical"]))} && git push origin HEAD:main'
    assert gated(monkeypatch, command, real_repos['unrelated']) == 2
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('command', [
    'git -c alias.ship=push ship origin HEAD:main',
    'git -calias.ship=push ship origin HEAD:main',
    'git --config-env=alias.ship=SHIP ship origin HEAD:main',
    'git ship origin HEAD:main',
])
def test_unresolved_git_alias_cannot_hide_publication(real_repos, monkeypatch, command):
    real_repos['git'](real_repos['canonical'], 'config', 'alias.ship', 'push')
    assert gated(monkeypatch, command, real_repos['canonical']) == 2
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('form', [
    'wrangler pages deploy dist --cwd {target}',
    'wrangler pages deploy dist --cwd={target}',
    'wrangler --cwd {target} pages deploy dist',
    'wrangler pages --cwd {target} deploy dist',
    'wrangler pages deployment --cwd {target} create dist',
    'wrangler pages deploy dist --config {target}/wrangler.toml',
])
def test_wrangler_target_options_never_consume_ambient_approval(real_repos, monkeypatch, form):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic preserved approval') == 0
    before = Path(pg.ledger_path()).read_bytes()
    command = form.format(target=shlex.quote(str(real_repos['linked'])))
    assert gated(monkeypatch, command, repo) == 2
    assert Path(pg.ledger_path()).read_bytes() == before


@pytest.mark.parametrize('command', [
    'wrangler pages publish dist',
    'wrangler pages deployment create dist',
    'npx wrangler pages publish dist',
    'wrangler pages deploy dist --dry-run',
    'wrangler pages publish dist --dry-run',
    'wrangler pages deploy dist -- --dry-run',
    'wrangler deploy index.js -- --dry-run',
    'wrangler versions deploy candidate@100%',
    'wrangler triggers deploy',
])
def test_wrangler_aliases_and_inactive_dry_run_flags_remain_guarded(real_repos, monkeypatch, command):
    # Wrangler Pages has no dry-run option. Worker dry-run is meaningful only
    # before the option terminator; the existing Worker positive control stays.
    assert gated(monkeypatch, command, real_repos['canonical']) == 2
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('data', ['release-gate.mjs deploy-pages', 'GIT_DIR=fake', 'PATH=fake', 'PUBLISH_GUARD_STATE_DIR=fake', '-v', '$(git push origin HEAD:main)'])
@pytest.mark.parametrize('separator', ['&&', ';'])
def test_literal_data_stays_data_beside_ordinary_publication(real_repos, monkeypatch, data, separator):
    words = ' '.join(shlex.quote(part) for part in data.split())
    command = f'printf "%s" {words} {separator} git push -q origin HEAD 2>&1 | tail -5; echo done'
    assert gated(monkeypatch, command, real_repos['unrelated']) == 0
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('path', ['/dev/stdin', '/dev/fd/0', '/proc/self/fd/0'])
@pytest.mark.parametrize('form', [
    "printf 'git push origin HEAD:main\\n' | bash {path}",
    "bash {path} <<'SCRIPT'\ngit push origin HEAD:main\nSCRIPT\n",
    "bash -- {path} <<'SCRIPT'\ngit push origin HEAD:main\nSCRIPT\n",
    ". -- {path} <<'SCRIPT'\ngit push origin HEAD:main\nSCRIPT\n",
])
def test_explicit_shell_stdin_script_paths_are_executable(real_repos, monkeypatch, path, form):
    assert gated(monkeypatch, form.format(path=path), real_repos['canonical']) == 2
    assert not real_repos['state'].exists()


@pytest.mark.parametrize('command', [
    'export GIT_DIR=fake && git push origin HEAD:main',
    'GIT_DIR=fake && git push origin HEAD:main',
    'builtin export GIT_DIR=fake && git push origin HEAD:main',
    'popd && git push origin HEAD:main',
    'git config remote.origin.url https://example.com/sites/public-site.git && git push origin HEAD:main',
    'printf -v GIT_DIR "%s" fake && git push origin HEAD:main',
    'printf "%s" fake > .git/config; git push origin HEAD:main',
    'printf "%s" "$(git remote set-url origin https://example.com/sites/public-site.git)" && git push origin HEAD:main',
])
def test_actual_state_changes_remain_unsafe_before_publication(real_repos, monkeypatch, command):
    assert gated(monkeypatch, command, real_repos['unrelated']) == 2


def test_substitution_cannot_change_the_head_after_approval_check(real_repos, monkeypatch):
    repo = real_repos['canonical']
    assert pg.approve(str(repo), 'Synthetic preserved approval') == 0
    before = Path(pg.ledger_path()).read_bytes()
    command = f'printf "%s" "$(git update-ref HEAD {real_repos["second"]})" && git push origin HEAD:main'
    assert gated(monkeypatch, command, repo) == 2
    assert Path(pg.ledger_path()).read_bytes() == before


@pytest.mark.parametrize('quote, expected', [('"', 2), ("'", 0)])
def test_shell_expansion_cannot_change_directory_lookup(real_repos, monkeypatch, quote, expected):
    monkeypatch.delenv('CDPATH', raising=False)
    expression = '${CDPATH:=' + str(real_repos['canonical'].parent) + '}'
    command = f'printf "%s" {quote}{expression}{quote} && cd public-site && git push origin HEAD:main'
    assert gated(monkeypatch, command, real_repos['unrelated'].parent) == expected


@pytest.mark.parametrize("command", [
    # BUG-6: the chain alone is classifiable; the dynamic fragment is what
    # makes the publication unmatchable to a ledger.
    'git commit -m "wip $(date +%s)" && git push origin HEAD:main',
    'git commit -m wip && git push origin $(git branch --show-current)',
    'FOO=1 git push origin HEAD:main',
])
def test_restricted_publication_names_policy_and_remedy(real_repos, monkeypatch, capsys, command):
    assert gated(monkeypatch, command, real_repos['unrelated']) == 2
    message = capsys.readouterr().err
    assert "deliberate policy" in message
    assert "own literal top-level command" in message
