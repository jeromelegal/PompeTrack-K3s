# ---------- BUILD ----------
FROM node:24-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./

RUN npm install --no-audit --no-fund

COPY . .

RUN npm run build


# ---------- RUNTIME ----------
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80