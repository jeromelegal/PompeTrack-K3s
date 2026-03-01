FROM alpine:3.19

# Installer dépendances
RUN apk add --no-cache \
    curl \
    ca-certificates \
    bash

# Installer kubectl (version stable automatiquement)
RUN KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt) \
    && curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && install -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Installer mc
RUN curl -LO https://dl.min.io/client/mc/release/linux-amd64/mc \
    && install -m 0755 mc /usr/local/bin/mc \
    && rm mc

ENTRYPOINT ["/bin/sh"]
