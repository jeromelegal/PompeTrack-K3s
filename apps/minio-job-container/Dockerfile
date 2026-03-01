FROM minio/mc:RELEASE.2025-08-13T08-35-41Z-cpuv1

USER root

# Installer kubectl
RUN curl -LO "https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

USER 1000
