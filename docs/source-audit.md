# Reproducible source audit

Run from the repository root with Python 3.12 and uv. The runner uses the `psql`
client, either locally with libpq environment variables or inside Docker:

```bash
ENOE_DOCKER_CONTAINER=postgres-dev PGDATABASE=enoe_microdatos \
  uv run python scripts/audit_source.py --output outputs/source-audit.json
```

For direct access, configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and a
protected `.pgpass` file; omit `ENOE_DOCKER_CONTAINER`. `.env.example` is a guide,
not automatically loaded configuration. Prefer a dedicated read-only role.
The Docker option uses the container's existing `POSTGRES_USER`; it does not
create a restricted role. The runner enforces a read-only repeatable-read
transaction, a 60-second statement timeout and a 180-second process timeout.

The SQL in `sql/source_audit.sql` exports only aggregates and schema metadata.
Output is ignored by Git and exclusive creation prevents overwrites. Each run
records capture time, database version, snapshot and query SHA-256. A snapshot
identifier is provenance, not a restorable input: the mutable database cannot
reproduce an old run without a separately retained source snapshot. The
[bounded raw audit](raw-join-audit.md) records hashes for three official
archives; the deployed ETL's complete input manifest and ingestion revision
remain to be established.

The semantic-consistency section separates missing exact income from reported
income bands and distinguishes zero hours during a temporary absence from other
zero-hour records. These are diagnostics against official code lists; they do
not silently recode the staged data.

The funnel is cumulative: step 0 is all rows in the audit window, 1 Jalisco,
2 complete interview, 3 accepted residency, 4 accepted age, 5 occupied, and
6 subordinate paid worker. Adjacent-step differences give exclusions. NULL
filter values fail the corresponding filter. The expected 14 quarters appear
even when absent, with zero records. `valid_weight_sum` excludes null/nonpositive
`fac`; `invalid_weights` explicitly counts them. Never sum quarterly totals to
claim a population of unique people.

Categorical outputs preserve raw codes and SQL NULL, with both records and
positive-weight sums. Divide each category by its variable-quarter total for
sample and weighted shares. Numeric summaries are raw and unweighted; special
codes have not been removed. NULL rates do not measure all survey nonresponse.
Design checks establish presence, not valid variance estimation. Informality
predicate disagreements are diagnostics, not an adjudication of definitions.

The natural-key check covers the post-ingestion table. It cannot prove original
SDEM–COE correspondence or detect records lost before insertion. The bounded
[raw join audit](raw-join-audit.md) now shows that the official shared key is
safe in the inspected archives while the current ETL key is not; this is why
Gate A remains blocked.

See [findings](audit-findings.md), the [Gate A decision](gate-a-decision.md),
and [implementation progress](implementation-progress.md).
Run all tests, including SQL fixtures without database writes:

```bash
ENOE_DOCKER_CONTAINER=postgres-dev PGDATABASE=enoe_microdatos \
  ENOE_TEST_POSTGRES=1 make check
```

Without `ENOE_TEST_POSTGRES=1`, local SQL integration tests are explicitly skipped.
CI enables them against an isolated PostgreSQL service. No production connection
or microdata is needed by the fixtures.
