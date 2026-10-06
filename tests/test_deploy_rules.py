"""R3.2 and R3.7: which commands deploy which site, and the date rules no approval overrides."""

import json
import re
import subprocess
import time
from pathlib import Path

import pytest

from synthesis import approvals, guards

FIX = json.loads((Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "incidents.json").read_text(encoding="utf-8"))
HOUR, DAY = 3600, 86400


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _stamp(when, fmt="%Y-%m-%dT%H:%M:%S"):
    return time.strftime(fmt, time.localtime(when))


def _post(site, slug, when, layout="flat_article_layout", date=None):
    shape = FIX[layout]
    t = time.localtime(when)
    rel = shape["path"].format(slug=slug, yyyy=f"{t.tm_year:04d}", mm=f"{t.tm_mon:02d}", dd=f"{t.tm_mday:02d}")
    path = site / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(shape["text"].replace("{date}", date or _stamp(when)), encoding="utf-8")
    return rel


def _commit(site, message="update"):
    _git(site, "add", "-A")
    _git(site, "commit", "-qm", message)


@pytest.fixture
def site(tmp_path):
    """A site repository published to origin/main, with one live post from last week."""
    root = tmp_path / "site"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    _post(root, "last-week", time.time() - 7 * DAY)
    _commit(root, "first post")
    subprocess.run(["git", "init", "-q", "--bare", str(tmp_path / "origin.git")], check=True)
    _git(root, "remote", "add", "origin", str(tmp_path / "origin.git"))
    _git(root, "push", "-q", "origin", "main")
    (tmp_path / "elsewhere").mkdir()
    return root


def _push(site, config=None, cwd=None):
    config = config or {"push_deploys": [str(site)]}
    return guards.check("Bash", {"command": f"git -C {site} push origin main"}, config, cwd=str(cwd or site.parent / "elsewhere"))


@pytest.fixture(autouse=True)
def _principal(principal):
    global _approve
    _approve = principal


# --- which command deploys which site ----------------------------------------------------------

def test_every_incident_shape_of_a_site_push_is_a_deploy(site):
    shapes = FIX["git_c_push"]
    elsewhere = site.parent / "elsewhere"
    for command in shapes["commands"]:
        command = command.replace("{site}", str(site))
        reason = guards.check("Bash", {"command": command}, {"push_deploys": [str(site)]}, cwd=str(elsewhere))
        assert reason and "production" in reason, command
    for command in shapes["not_pushes"]:
        command = command.replace("{site}", str(site))
        assert guards.check("Bash", {"command": command}, {"push_deploys": [str(site)]}, cwd=str(elsewhere)) is None, command


def test_a_push_is_attributed_to_the_directory_the_command_names(site, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    config = {"push_deploys": [str(site)]}
    assert guards.check("Bash", {"command": f"cd {site} && git push"}, config, cwd=str(other)) is not None
    assert guards.check("Bash", {"command": f"cd {site} && cd {other} && git push"}, config, cwd=str(other)) is None
    assert guards.check("Bash", {"command": "git push"}, config, cwd=str(other)) is None
    assert guards.check("Bash", {"command": "git push"}, config, cwd=str(site / "astro-site")) is not None
    assert guards.check("Bash", {"command": f"(cd {site} && npm run build); git push"}, config, cwd=str(other)) is None


def test_a_push_from_a_linked_worktree_of_a_site_is_a_deploy(site, tmp_path):
    _git(site, "worktree", "add", "-q", str(tmp_path / "site-wt"), "-b", "fix")
    assert _push(tmp_path / "site-wt", config={"push_deploys": [str(site)]}) is not None


@pytest.mark.parametrize("command", [
    "cat > notes.md <<'EOF'\nrm -rf ~\ngit push origin main\nEOF\nls",       # a file being written, not run
    "git commit -m \"$(cat <<'EOF'\nfix site push\nEOF\n)\"",
    "diff <(git -C {site} show HEAD:a.md) <(cat a.md)",                    # read-only shapes the old guard refused
    "for f in *.md; do grep -c push \"$f\"; done",
    "cd {site} && git log --oneline | head -3 2>&1",
])
def test_text_that_only_mentions_a_push_or_a_delete_is_neither(site, command):
    command = command.replace("{site}", str(site))
    assert guards.check("Bash", {"command": command}, {"push_deploys": [str(site)]}, cwd=str(site)) is None


@pytest.mark.parametrize("command", ["bash <<'EOF'\nrm -rf ~\nEOF", "cat <<EOF | sh\ncd {site} && git push\nEOF",
                                     "cd {elsewhere} && echo hi\nrm -rf ~"])
def test_a_heredoc_fed_to_a_shell_and_a_later_line_are_still_checked(site, command):
    command = command.replace("{site}", str(site)).replace("{elsewhere}", str(site.parent / "elsewhere"))
    assert guards.check("Bash", {"command": command}, {"push_deploys": [str(site)]}, cwd=str(site.parent)) is not None


def test_a_build_deploy_inside_a_wrapper_shell_targets_the_site_it_names(site):
    _post(site, "tomorrow", time.time() + DAY)  # untracked, so only a build deploy sees it
    command = f"bash -lc 'cd {site} && npx wrangler pages deploy dist --project-name=site'"
    assert "before its stated date" in guards.check("Bash", {"command": command}, {}, cwd=str(site.parent / "elsewhere"))


# --- a page never goes live before its date ----------------------------------------------------

@pytest.mark.parametrize("layout", ["flat_article_layout", "nested_article_layout"])
def test_a_future_dated_post_is_refused_in_both_layouts(site, layout):
    rel = _post(site, "tomorrow", time.time() + DAY, layout)
    _commit(site)
    reason = _push(site)
    assert "never go live before its stated date" in reason and rel in reason
    assert not (approvals.paths.state() / "approval-requests").exists()  # no approval is even asked for


def test_an_approved_deploy_is_still_refused_and_its_approval_is_not_spent(site):
    command = f"cd {site} && npx wrangler pages deploy dist"
    elsewhere = str(site.parent / "elsewhere")
    _approve(guards.check("Bash", {"command": command}, {}, cwd=elsewhere))
    early = site / _post(site, "early", time.time() + 2 * HOUR)  # untracked: HEAD, and so the approval, unchanged
    assert "before its stated date" in guards.check("Bash", {"command": command}, {}, cwd=elsewhere)
    early.unlink()
    assert guards.check("Bash", {"command": command}, {}, cwd=elsewhere) is None


def test_a_few_minutes_ahead_is_clock_skew_not_a_future_post(site):
    _post(site, "now", time.time() + 5 * 60)
    _commit(site)
    assert "production" in _push(site)


def test_a_date_with_a_zone_is_read_in_that_zone(site):
    ahead = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 2 * HOUR))
    _post(site, "zoned", 0, date=ahead)
    _commit(site)
    assert "before its stated date" in _push(site)


def test_a_date_only_post_for_tomorrow_is_refused(site):
    _post(site, "tomorrow", 0, date=_stamp(time.time() + 2 * DAY, "%Y-%m-%d"))
    _commit(site)
    assert "before its stated date" in _push(site)


# --- a published date never changes ------------------------------------------------------------

def test_redating_a_live_post_is_refused_naming_both_dates(site):
    live = time.time() - 7 * DAY
    _post(site, "last-week", live - DAY)
    _commit(site, "redate")
    reason = _push(site)
    assert "Published dates never change" in reason
    assert _stamp(live, "%Y-%m-%d %H:%M") in reason and _stamp(live - DAY, "%Y-%m-%d %H:%M") in reason


def test_editing_a_live_post_without_moving_its_date_is_an_ordinary_deploy(site):
    page = site / FIX["flat_article_layout"]["path"].format(slug="last-week")
    text = page.read_text(encoding="utf-8")
    date_line = next(line for line in text.splitlines() if line.startswith("date:"))
    same_moment = date_line.replace("T", " ")  # the same moment written another way
    page.write_text(text.replace(date_line, same_moment).replace("Body text.", "Corrected body text."), encoding="utf-8")
    _post(site, "new-today", time.time() - HOUR)
    _commit(site, "edit and add")
    assert "production" in _push(site)


def test_without_the_published_branch_the_redate_check_refuses_instead_of_guessing(site, tmp_path):
    _git(site, "update-ref", "-d", "refs/remotes/origin/main")
    assert "fetch origin" in _push(site)
    _git(site, "remote", "remove", "origin")  # never published anywhere: nothing live to protect
    assert "production" in _push(site)


def test_a_malformed_content_config_fails_closed(site):
    reason = _push(site, config={"push_deploys": [str(site)], "deploy_content": "content/**"})
    assert "deploy_content" in reason


# --- approval binding and the rapid-redeploy brake ---------------------------------------------

def test_an_approval_is_bound_to_the_commit_it_was_given_for(site):
    _approve(_push(site))
    _post(site, "later", time.time() - HOUR)
    _commit(site, "one more")
    assert _push(site) is not None


def test_a_second_deploy_within_45_minutes_needs_its_own_rapid_approval(site, monkeypatch):
    _approve(_push(site))
    assert _push(site) is None  # first deploy goes out and is recorded
    reason = _push(site)
    assert "within 45 minutes" in reason and "rapid" in reason
    assert approvals.grant_from_prompt("approve abcdef") == []
    granted = _approve(reason)
    assert granted and granted[0].startswith("RAPID redeploy")
    assert _push(site) is None
    real = time.time
    monkeypatch.setattr(guards.time, "time", lambda: real() + 46 * 60)
    reason = _push(site)
    assert "production" in reason and "rapid" not in reason


def test_a_rapid_approval_still_counts_if_the_window_closes_before_the_rerun(site):
    _approve(_push(site))
    _push(site)
    _approve(_push(site))
    identity = str(site.resolve())
    guards._last_deploy(identity).write_text(f"{identity}\n{time.time() - 46 * 60}\n", encoding="utf-8")
    assert _push(site) is None


def test_linked_worktrees_share_the_brake_with_their_main_checkout(site, tmp_path):
    _approve(_push(site))
    _push(site)
    _git(site, "worktree", "add", "-q", str(tmp_path / "site-wt"), "-b", "fix")
    assert "within 45 minutes" in _push(tmp_path / "site-wt", config={"push_deploys": [str(site)]})


def test_one_command_deploying_a_site_twice_is_refused_before_any_approval(site):
    reason = guards.check("Bash", {"command": f"git -C {site} push origin main && git -C {site} push origin main"},
                          {"push_deploys": [str(site)]}, cwd=str(site.parent / "elsewhere"))
    assert "more than once" in reason and "approve" not in reason


def test_a_site_that_renders_another_repository_checks_that_repository_s_dates(site, tmp_path):
    other = tmp_path / "other-site"
    subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
    _post(other, "tomorrow", time.time() + DAY)  # uncommitted: the build reads the working tree
    config = {"push_deploys": [str(site)], "deploy_also_renders": {str(site): [str(other)]}}
    reason = _push(site, config)
    assert "never go live before its stated date" in reason
    assert "approve" in _push(site, {"push_deploys": [str(site)]})  # without the mapping, an ordinary deploy
