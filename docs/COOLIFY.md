# Coolify Deployment (Backend)

This guide explains how to run the decomp.me backend in [Coolify](https://coolify.io/) using the production Docker image published to GHCR.

## Container Image

- Image name: `ghcr.io/decompme/decompme-backend`
- Tags:
  - `prod-latest`: latest build from the `main` branch.
  - `prod-{git-sha}`: immutable image for each commit.
- Port exposed: `8000`

## Environment

Configure these variables in Coolify:

- `SECRET_KEY`: Django secret key (required).
- `DATABASE_URL`: e.g. `postgresql://user:password@postgres:5432/decompme`.
- `ALLOWED_HOSTS`: comma-separated host list (`backend.example.com` etc.).
- `USE_SANDBOX_JAIL=on`
- `SANDBOX_DISABLE_PROC=true`
- `COMPILER_BASE_PATH=/backend/compilers`
- `LIBRARY_BASE_PATH=/backend/libraries`
- `LOCAL_FILE_DIR=/backend/local_files`
- `WINEPREFIX=/tmp/wine`
- Optional hardening: `SECURE_SSL_REDIRECT=true`, `SECURE_PROXY_SSL_HEADER=true`.

`DATABASE_HOST`/`DATABASE_PORT` can be set if you prefer them over `DATABASE_URL`.

## Persistent Volumes

Mount the following directories to Coolify persistent volumes so compiler and library assets survive restarts:

| Mount Path                | Purpose                            |
| ------------------------- | ---------------------------------- |
| `/backend/compilers`      | Cached toolchains                  |
| `/backend/libraries`      | Cached library archives            |
| `/backend/local_files`    | Scratch uploads                    |
| `/backend/static`         | Django static files (admin assets) |
| `/backend/media` *(opt.)* | Optional media uploads             |

Ensure the volumes are owned by UID/GID `1000` (the `ubuntu` user inside the container). In Coolify set the "Container User" to `1000`.

## Initialising Toolchains

After the service starts the first time, run these one-off tasks from the Coolify console (or `docker exec`) to populate compilers and libraries:

```bash
cd /backend
uv run compilers/download.py --compilers-dir /backend/compilers
uv run libraries/download.py --libraries-dir /backend/libraries
```

You can rerun them later to pick up updates. The entrypoint will run database migrations automatically on every start.

## Health Check

Expose port `8000` in Coolify. A simple HTTP GET to `/api/` returns JSON when the backend is healthy.

## Optional: Static Assets

If you serve the Django admin through Coolify, collect static files into the persistent volume:

```bash
cd /backend
uv run python manage.py collectstatic --noinput
```

The static directory can then be served by a reverse proxy (Coolify HTTP service, Nginx, etc.).
