# The PR-queue helper

How `scripts/pr_queue.py` scans a Bitbucket repository's open pull requests for the daily-rituals PR-queue scan, kept as written in 1.2.2.

## PR queue

`scripts/pr_queue.py` is the Bitbucket half of the daily-rituals PR-queue scan (`synthesis-daily-rituals/scripts/pr_queue_scan.py`), which dispatches each declared repo by origin host and loads this helper by path.

- `list_open_prs(workspace, repo_slug)` uses the explicitly bound `bkt api /repositories/<workspace>/<slug>/pullrequests` GET with reviewer fields requested. It classifies a complete inventory as awaiting your review, your own open PRs, or open PRs nobody was asked to review. The ordinary PR-list response omits reviewer fields and cannot establish an empty reviewer list.
- Identity comes from `bkt api /user --json` (`uuid`, `account_id`, `username`), matched on `uuid` and `account_id` only. Resolve it once with `bkt_identity()` and pass it through when scanning many repos.
- Pagination is bounded to 100 pages of 50 rows within 20 seconds for the repository. Every continuation must retain the repository and query scope. Missing reviewer identities, repeated PR IDs, incomplete pagination, a 404, non-zero exit, timeout, or unparseable body returns `{"status": "unscanned", "reason": ...}` with no partial `items`. Only an explicit complete empty inventory is an empty queue.
- Read-only. Tests inject a `runner` and never reach `bkt`.
