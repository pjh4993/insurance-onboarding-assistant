# The design docs as a static site, served at the root of the docs host. Built from the repo root:
#   docker build -f docs-site/Dockerfile .

FROM python:3.13-slim AS build
# Same pins as the Makefile's `make docs`.
RUN pip install --no-cache-dir mkdocs-material==9.7.7 mkdocs-same-dir==0.1.5 mkdocs-awesome-nav==3.3.0 mkdocs-glightbox==0.5.1
WORKDIR /src
COPY mkdocs.yml .nav.yml README.md CONTRACTS.md ./
COPY .mkdocs .mkdocs
COPY docs docs
COPY contracts contracts
RUN DISABLE_MKDOCS_2_WARNING=true mkdocs build --strict --site-dir /site

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY docs-site/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO /dev/null http://127.0.0.1:8080/ || exit 1
