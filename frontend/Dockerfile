# syntax=docker/dockerfile:1

# --- deps: nur Abhängigkeiten installieren, damit dieser Layer bei reinen
# Quellcode-Änderungen aus dem Cache kommt -------------------------------- #
FROM node:22.15.1-alpine3.21 AS deps
WORKDIR /frontend

COPY package.json package-lock.json ./
# eslint@10.7.0 (root) im Vergleich zu dem in eslint-config-next@16.2.10 enthaltenen
# eslint-plugin-import/jsx-a11y/react, dessen Peer-Range bei eslint@^9 endet.
RUN npm ci --legacy-peer-deps

# --- builder: Next.js-Build mit den zur Build-Zeit inzulinenden
# NEXT_PUBLIC_*-Variablen ---------------------------------------------------#
FROM node:22.15.1-alpine3.21 AS builder
WORKDIR /frontend

ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /frontend/node_modules ./node_modules
COPY . .
RUN npm run build

# --- runner: nur das eigenständige Standalone-Bundle, kein npm/node_modules #
FROM node:22.15.1-alpine3.21 AS runner
WORKDIR /frontend

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /frontend/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
