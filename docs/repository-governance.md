# Repository governance

## Main branch

The intended configuration is versioned in
[`branch-protection.json`](../.github/branch-protection.json). A maintainer applies
it through GitHub's API; committing this file alone does not configure GitHub.

- Changes require a PR, including changes made by administrators.
- The `Quality` check from GitHub Actions must pass.
- The PR branch must be current with `main` before merging.
- Review conversations must be resolved.
- History must be linear; squash is the only enabled merge method.
- Force pushes and branch deletion are blocked.
- Remote issue branches are deleted automatically after merge.

There is initially one maintainer, so zero external approvals are required.
This permits self-authored PRs while retaining checks and PR-only integration.
Consider one required approval once an independent reviewer is available.
Issue linkage and English are review requirements, not automated enforcement.

## Apply and inspect protection

With administrator permission, after the named check has run:

```bash
gh api --method PUT repos/guadaloop-07/job-quality-enoe/branches/main/protection \
  --input .github/branch-protection.json
gh api repos/guadaloop-07/job-quality-enoe/branches/main/protection
```

The check name is part of this contract. Update protection deliberately if the
workflow job name changes. Never disable protection to work around failed checks.

## Tooling and access

CI uses read-only contents permissions and actions pinned to commit SHAs.
Private-key detection and GitHub secret scanning help prevent accidental exposure
but do not replace review. Do not include live data or credentials in issues,
logs, notebooks, or PRs.

Dependabot proposes updates; maintainers link proposals to issues and review
them through the usual workflow. Dependency updates never auto-merge.

References: [GitHub branch protection](https://docs.github.com/en/rest/branches/branch-protection),
[pre-commit](https://pre-commit.com/), and
[uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/).
