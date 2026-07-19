# Deploy OrbitWatch on Easypanel

This guide deploys the full OrbitWatch stack (PostgreSQL, Redis, MinIO, backend, worker, frontend) using Easypanel's **Compose** service.

## 1. Prerequisites

- An Easypanel instance (self-hosted or managed)
- A server with Docker support
- A domain (or subdomain) to point at the frontend
- Strong secrets ready for the environment variables

## 2. Prepare the repository

Fork or import the repository into your GitHub/Git account:

```bash
https://github.com/ddlidded/orbitwatch
```

## 3. Create the Easypanel project

1. Log into Easypanel.
2. Click **Create New Project** and name it (e.g., `orbitwatch`).
3. Inside the project, create a **Compose** service.
4. Choose the **GitHub repository** source and select `ddlidded/orbitwatch` (or your fork).
5. When prompted for the Docker Compose file path, enter:

   ```
   docker-compose.easypanel.yml
   ```

## 4. Configure environment variables

In the Easypanel **Environment** section, set at least these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_USER` | Postgres username | `orbitwatch` |
| `POSTGRES_PASSWORD` | **Strong** Postgres password | generate one |
| `POSTGRES_DB` | Postgres database name | `orbitwatch` |
| `SECRET_KEY` | FastAPI signing/encryption key | generate a 64-char random string |
| `CORS_ORIGINS` | Your frontend domain(s), comma-separated | `https://orbitwatch.yourdomain.com` |
| `S3_ACCESS_KEY` | MinIO root username | `minioadmin` |
| `S3_SECRET_KEY` | **Strong** MinIO root password | generate one |
| `S3_BUCKET` | MinIO bucket name | `orbitwatch` |

Optional but recommended:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Override the default Postgres URL |
| `REDIS_URL` | Override the default Redis URL |
| `S3_ENDPOINT` | Override the default MinIO URL |
| `S3_REGION` | `us-east-1` |

The defaults in `docker-compose.easypanel.yml` are safe for internal networking but must be overridden with real secrets.

## 5. Bind a domain

1. In Easypanel, go to the **Domains** tab of the `frontend` service.
2. Add your domain (e.g., `orbitwatch.yourdomain.com`).
3. Select port `80` as the proxy target.
4. Easypanel will provision a Let's Encrypt certificate automatically.

If you want direct access to the backend API or MinIO console, bind additional domains to those services on the same compose stack:

- `backend` on port `8000`
- `minio` on port `9001` (console) or `9000` (S3 API)

Normally only the `frontend` domain is required because Nginx proxies `/api`, `/docs`, `/openapi.json`, and `/ws` to the backend.

## 6. Deploy

Click **Deploy**. Easypanel will build the backend and frontend images and start all services.

Wait until all containers report healthy:

- `postgres` — `pg_isready`
- `redis` — `redis-cli ping`
- `minio` — MinIO health endpoint
- `backend` — `/healthz`
- `worker` and `frontend` start after backend is ready

## 7. Initial login

Once the deployment is green, open your frontend domain and log in with the default admin account:

- **Email:** `admin@isotopiq.dev`
- **Password:** `OrbitWatch-Admin-2024!`

Change this password immediately under **Settings → User Management** or the **Profile** page.

## 8. Connect the instrument agent

On the Windows instrument PC:

1. Build or publish `agent/OrbitWatchAgent`.
2. Edit `agent/OrbitWatchAgent/appsettings.json`:

   ```json
   {
     "Agent": {
       "BackendUrl": "https://orbitwatch.yourdomain.com/api/v1",
       "Mode": "helios"
     }
   }
   ```

3. Run the agent.

For replay/dev mode, use `"Mode": "replay"`.

## 9. Updating the deployment

When you push changes to the connected Git branch, Easypanel can auto-redeploy if **Auto Deploy** is enabled. Otherwise, click **Redeploy** in the Easypanel UI.

## Troubleshooting

- **Backend fails to start:** Check that `SECRET_KEY` and `POSTGRES_PASSWORD` are set and `DATABASE_URL` matches.
- **Frontend shows blank/API errors:** Verify `CORS_ORIGINS` includes your exact domain (`https://` if using HTTPS).
- **MinIO not accessible:** Ensure `S3_ACCESS_KEY` and `S3_SECRET_KEY` are set and the `minio` healthcheck passes.
- **Agent cannot connect:** Confirm the agent `BackendUrl` points to the frontend domain (or a backend domain) and includes `/api/v1`.
