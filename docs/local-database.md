# Independent local database

This repository owns an empty PostgreSQL 17 database for the personal ENOE
analysis. It is separate from `postgres-dev`, `iieg_postgres`, ETL-SIEEJ, and
their volumes. Do not copy, dump, or connect this environment to those systems.
Issue #8 will load official ENOE archives directly into this database.

## Initial setup

Docker Compose and `uv` are required. Create a private local configuration, then
replace the template password with a credential used only for this database:

```bash
cp .env.example .env
# Edit .env locally; it is ignored by Git.
just db-up
just db-status
just db-migrate
just db-test
```

The default host binding is `127.0.0.1:5435`. Change `POSTGRES_PORT` in `.env`
when that port is occupied. The health check uses `pg_isready`; `just db-status`
shows the service state. `just db-migrate` is safe to re-run: it stores each
migration filename and SHA-256 in `metadata.schema_migrations`, and rejects a
recorded migration whose contents later change.

To inspect the Compose structure without substituting or displaying local
configuration values, run:

```bash
just db-config
```

`just db-down` stops the service but preserves the named `postgres_data` volume.
Starting it again with `just db-up` resumes the same database. Do not use
`docker compose down -v` unless you have intentionally backed up and decided to
destroy all local database state; it removes the volume.

## Backup and restore

Backups can contain microdata after issue #8, so store them outside this
repository and outside Git. With the database running, create a custom-format
backup from the host:

```bash
docker compose --env-file .env -f compose.yaml exec -T db sh -ec \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > /safe/location/enoe-local.backup
```

Restore only into an intentionally chosen database; this command does not clean
or delete existing objects for you:

```bash
docker compose --env-file .env -f compose.yaml exec -T db sh -ec \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error --no-owner' \
  < /safe/location/enoe-local.backup
```

Run `just db-migrate` and `just db-test` after a restore. Review the archive
location and destination before either command; neither backup files nor raw
survey data belong in Git.

## Rotate a local credential

Changing `POSTGRES_PASSWORD` in `.env` alone does not change the existing
database role. While the database is running, use PostgreSQL's interactive
password prompt, then update `.env` to the same new value:

```bash
docker compose --env-file .env -f compose.yaml exec db sh -ec \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\password"'
```

The prompt avoids displaying the new password in the command or terminal log.
Keep `.env`, backups, downloaded archives, and Docker volumes private.
