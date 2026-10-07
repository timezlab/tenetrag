# Local stack: Neo4j and Postgres in Docker Compose

`deploy/` runs Neo4j and Postgres (with pgvector) on your machine, in one
of two modes. The backend and frontend of the TenetRAG UI will join the
production mode later, so you can host the interface as well as the SDK.

You need Docker Engine with Compose v2 (`docker compose`). Run every
command from the repository root.

| | Development | Production |
|---|---|---|
| Files | `compose.yaml` + `compose.dev.yaml` | `compose.yaml` + `compose.prod.yaml` |
| Start, stop | `make dev-up`, `make dev-down` | `make prod-up`, `make prod-down` |
| Passwords | variables in `deploy/.env` | secret files |
| Restart after a crash or reboot | no | yes (`unless-stopped`) |
| Memory limits | none | Neo4j 3 GB, Postgres 2 GB |
| Container logs | Docker's default | rotated, 5 files of 10 MB |
| Compose project, and so volumes | `tenetrag-dev` | `tenetrag` |
| Ports | 127.0.0.1 only | 127.0.0.1 only |

Both modes run the images that the integration tests pin by digest:
`neo4j:2026.09.0-community` and `pgvector/pgvector:0.8.7-pg17`. Neo4j
usage reports are off, as is the driver's telemetry.

## Development

1. Copy the example and set both passwords. Neo4j needs 8 characters or
   more. Compose refuses to start while either is empty.

   ```sh
   cp deploy/.env.example deploy/.env
   $EDITOR deploy/.env
   ```

2. Start the stack. `make dev-up` returns once both healthchecks pass.

   ```sh
   make dev-up
   ```

3. Connect from the SDK. The profile names the variables, never the
   values, so export them first:

   ```yaml
   # profile.yaml
   connections:
     graph:
       kind: neo4j
       uri: bolt://localhost:7687
       credential: {kind: basic, user: neo4j, password_env: NEO4J_PASSWORD}
     vectors:
       kind: postgres
       host: localhost
       database: tenetrag
       credential: {kind: basic, user: tenetrag, password_env: POSTGRES_PASSWORD}
   ```

   ```python
   from tenetrag.config import load_profile
   from tenetrag.storage import open_connection

   profile = load_profile("profile.yaml")
   for name, settings in profile.connections.items():
       with open_connection(settings, name=name) as connection:
           print(name, connection.health())
   ```

   ```sh
   set -a; . deploy/.env; set +a      # exports NEO4J_PASSWORD and POSTGRES_PASSWORD
   uv run python check.py
   ```

   `auto` TLS allows plain connections to `localhost`, so no TLS setup is
   needed here.

4. Stop it with `make dev-down`. The data stays in the volumes. To delete
   it too:

   ```sh
   docker compose -f deploy/compose.yaml -f deploy/compose.dev.yaml down -v
   ```

To run one store only, name it:
`docker compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d --wait neo4j`.

## Production

1. Create the secret files. `neo4j_auth` holds `neo4j/<password>` on one
   line. With another format, the Neo4j image prints the value to its
   log when it refuses it.

   ```sh
   install -d -m 700 deploy/secrets
   python3 -c 'import secrets; print("neo4j/" + secrets.token_urlsafe(24), end="")' \
     > deploy/secrets/neo4j_auth
   python3 -c 'import secrets; print(secrets.token_urlsafe(24), end="")' \
     > deploy/secrets/postgres_password
   chmod 644 deploy/secrets/neo4j_auth deploy/secrets/postgres_password
   ```

   The files must be readable by everyone (644), because the Neo4j image
   checks the file as its own user, whose id differs from yours. The 700
   directory keeps other users of the machine out. git ignores
   `deploy/secrets/`. To keep the files outside the checkout, set
   `TENETRAG_SECRETS_DIR` in `deploy/.env`.

2. Start the stack:

   ```sh
   make prod-up
   ```

3. Give the SDK the same passwords:

   ```sh
   export NEO4J_PASSWORD="$(cut -d/ -f2- deploy/secrets/neo4j_auth)"
   export POSTGRES_PASSWORD="$(cat deploy/secrets/postgres_password)"
   ```

4. Tune memory in `deploy/.env` if needed: `NEO4J_HEAP_SIZE` and
   `NEO4J_PAGECACHE_SIZE` (1g each by default), and the container limits
   `NEO4J_MEMORY_LIMIT` (3g) and `POSTGRES_MEMORY_LIMIT` (2g). Keep the
   Neo4j limit above heap plus page cache.

## Notes

- **Both modes at once.** They keep separate volumes but use the same
  host ports by default. Set `NEO4J_BOLT_PORT`, `NEO4J_HTTP_PORT` and
  `POSTGRES_PORT` for one of them.
- **Restarts in production mode.** Docker restarts a store whose process
  exits, a crash included. It does not restart one you stopped yourself
  with `docker stop` or `docker kill`; `make prod-up` starts it again.
- **Upgrading an image.** Change `tests/integration/conftest.py` and
  `deploy/compose.yaml` together. `tests/unit/test_local_stack.py` fails
  until the two match.
- **Postgres extensions.** `vector` and `pg_trgm` ship in the image, and
  `health()` checks that both are available.
- **`PG*` variables.** The SDK connects only to the host in the profile,
  whatever `PGHOSTADDR` says. It refuses to open while `PGOPTIONS` or
  `PGSERVICE` is set, since either can change the session; unset them for
  the process that runs TenetRAG ([research R12](../../specs/001-sdk-foundation/research.md), As built).
- **Coming later.** The production mode gains the backend and frontend
  that serve the TenetRAG UI. The development mode gains a backend
  service that runs from the mounted code and reloads on change.
