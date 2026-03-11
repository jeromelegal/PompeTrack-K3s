FROM node:24-slim

WORKDIR /src

RUN apt-get update && apt-get install -y build-essential python3 python3-pip --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./

ENV NODE_ENV=development

RUN npm install --no-audit --no-fund

COPY . .

RUN cp .env .env || true
# RUN npm run build:bots

COPY ./src/entrypoint.sh /src/entrypoint.sh
RUN chmod +x /src/entrypoint.sh
# ENTRYPOINT ["/src/entrypoint.sh"]

EXPOSE 3020
ENTRYPOINT ["npm", "run", "dev"]