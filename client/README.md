# Monitoring dashboard

React and TypeScript dashboard for the monitoring backend. It reads the existing host, metric history, Docker container, and application health APIs; it does not send or store metrics.

## Run locally

```sh
cd client
npm install
cp .env.example .env.local
npm run dev
```

Set `VITE_API_BASE_URL` in `.env.local` to the backend origin (for example, `http://localhost:8000`). The frontend appends the existing `/api/...` routes. Restart Vite after changing the environment file. The backend CORS allowlist is configured with `CORS_ORIGINS` in `server/.env` as a comma-separated list of frontend origins; the server example includes the standard local Vite development and preview origins.

The dashboard refreshes host data every 30 seconds. Host presence is inferred from `last_seen_at` (online when seen within two minutes); the dashboard presents the most recently reported readings and does not write to the backend.
