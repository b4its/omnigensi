FROM node:22-alpine AS base

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

# Dependencies first (better layer caching)
COPY package.json pnpm-lock.yaml .npmrc pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# ---------------------------------------------------------------------------
# development: vite dev server with HMR, exposed on 5296
# ---------------------------------------------------------------------------
FROM base AS development

ENV NODE_ENV=development
ENV PUBLIC_API_URL=http://localhost:8123

EXPOSE 5296

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:5296/ || exit 1

CMD ["pnpm", "run", "dev", "--host", "0.0.0.0", "--port", "5296"]

# ---------------------------------------------------------------------------
# production: build + preview server, non-root user
# ---------------------------------------------------------------------------
FROM base AS production

ENV NODE_ENV=production
ENV PUBLIC_API_URL=http://localhost:8123

RUN pnpm run build \
    && addgroup -S appgroup \
    && adduser -S appuser -G appgroup \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 5296

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:5296/ || exit 1

CMD ["pnpm", "run", "preview", "--host", "0.0.0.0", "--port", "5296"]
