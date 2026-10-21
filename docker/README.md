# Docker Infrastructure for Omnigensi

This directory contains container infrastructure configurations.
To start the entire stack:

```bash
docker compose up -d
```

Services:
- **postgres**: PostgreSQL 16 on port 5435 (host) / 5432 (container)
- **redis**: Redis 7 on port 6382 (host) / 6379 (container)
- **backend**: FastAPI application on port 8000
- **frontend**: SvelteKit application on port 5173
