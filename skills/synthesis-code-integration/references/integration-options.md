# Code integration: integration options

How to credit contributors, order several PRs, fall back when cherry-picking fails, and choose how much to adapt.

## Contributor Attribution

GitHub's contributor graph counts commits where you are the **author**. Custom text like `Contributor: Name (PR #5)` in the commit body is human-readable but GitHub does not parse it.

Use `Co-authored-by` trailers, which GitHub officially recognizes:

```
feat: add product description field to content pipeline

Integrates product description generation with writer guidance support.

Co-authored-by: Contributor Name <contributor@example.com>
```

The attribution model should match the integration intensity:

- **Full adopt-and-adapt** (substantial rework): Lead as commit author, contributor as `Co-authored-by`.
- **Lighter-touch integration** (minor adjustments): Contributor as commit `--author`, lead as `Co-authored-by`.
- **Merge-then-refine** (editorial improvements after merge): PR merge preserves contributor's commits. Lead's follow-up commit is separate, referencing the PR.
- **Direct merge** (zero-adjustment): Standard PR merge flow.

Attribution is not decoration. Developers use contribution graphs for career advancement. A workflow that funnels all commits through the lead's name effectively erases contributors from the project's visible history.

---

## Integrating Multiple PRs

When integrating more than two or three PRs in a session, ordering becomes a design decision.

### Dependency-Aware Ordering

1. **Independent PRs first.** Zero-overlap PRs validate the integration pipeline before tackling complex merges.
2. **Within a subsystem, simpler PR first.** When multiple PRs modify the same files, integrate the smaller one first.
3. **Read the merged result fresh.** After auto-merge resolves conflicts, read the merged code as if reviewing it for the first time. Auto-merged regions can produce semantic errors that no tool will flag.

### Cross-PR Test Failures

Each PR may pass its own CI independently. The synthesis merge still catches failures caused by cross-PR interactions. Run the **full** test suite on the integration branch.

---

## Fallback: Selective File Checkout

When a contributor's branch has a complex commit history (multiple renames, moves, reorganizations), cherry-picking may fail with rename/delete conflicts.

When the desired change is a known set of **new** files:

```bash
# 1. Identify what files actually changed
git diff --name-only main...contributor/branch

# 2. Checkout only those specific files
git checkout contributor/branch -- path/to/new/file1 path/to/new/file2

# 3. Commit with attribution
git commit -m "integrate PR #N: description

Co-authored-by: Contributor Name <contributor@example.com>"
```

**When to use:** Docs-only PRs with messy history, configuration file additions, any PR where `git diff --name-only` shows a small obvious set of new files.

**When NOT to use:** Changes that modify existing files (you would overwrite main's version), changes where semantic conflicts are possible.

---

## Evolution of Integration Intensity

### Phase 1: Full Adopt-and-Adapt

The lead creates a fresh integration branch, selectively brings in changes, and fixes every issue during integration.

**When appropriate:** First contributions from a new contributor. Contributions touching sensitive areas. Contributions built against significantly stale `main`.

### Phase 2: Lighter-Touch Integration

The lead merges with minor adjustments. The contributor's code structure is preserved.

**When appropriate:** Contributor has had at least one round of detailed review feedback. Issues are minor and localized.

### Phase 3: Merge-then-Refine

The lead merges the PR directly via GitHub, preserving the contributor's commits and authorship. Then creates a separate follow-up commit with editorial improvements, referencing the original PR.

**When appropriate:** Contribution is PR-based and high quality. The contributor did the creative work and deserves primary credit — first contributions, open-source visibility, career attribution. The lead's changes are editorial or cosmetic, not structural.

**When NOT appropriate (use Phase 1 instead):** Lead's changes are structural — different approach, architectural redesign. Branch is significantly stale. Security issues require pre-merge remediation.

**Workflow:**
1. Merge the PR via GitHub (`gh pr merge N --merge` or `--rebase`)
2. Create a separate follow-up commit with improvements, attributed to the lead
3. Commit message references the original PR: `Refinements to #N`

### Phase 4: Direct Merge with Review

Standard pull request workflow. The contributor submits, gets peer and lead review, and it merges directly.

**When appropriate:** Contributor consistently meets the quality bar across multiple contributions.

### Adjusting in Both Directions

The phases are not permanent promotions. If a contribution introduces a security gap or regression, intensity goes back up.

**Upgrade signal:** Fewer than half the issues of the previous round, and those issues are cosmetic.

**Downgrade signal:** A contribution introduces a security gap, architectural regression, or bundled unrelated changes.

### Choosing Between Lighter-Touch and Merge-then-Refine

| Factor | Lighter-Touch (Phase 2) | Merge-then-Refine (Phase 3) |
|--------|------------------------|-----------------------------|
| Contribution source | Branch cherry-pick or non-PR | PR-based contribution |
| Lead's changes | Interleaved with contributor's code | Separable from contributor's code |
| Git blame accuracy | Single combined commit | Per-line attribution preserved |
| GitHub merge event | No PR merge recorded | PR shows as merged, contributor credited |
