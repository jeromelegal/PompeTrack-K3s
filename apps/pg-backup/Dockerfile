# Dockerfile
FROM postgres:16-alpine

RUN apk add --no-cache curl bash \
  && curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc \
     -o /usr/local/bin/mc \
  && chmod +x /usr/local/bin/mc

CMD ["/bin/bash"]
