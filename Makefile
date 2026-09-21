# Docs site. The tools run from an ephemeral uvx environment, pinned here, so nothing is installed.
MKDOCS = DISABLE_MKDOCS_2_WARNING=true uvx \
	--with mkdocs-material==9.7.7 \
	--with mkdocs-same-dir==0.1.5 \
	--with mkdocs-awesome-nav==3.3.0 \
	--with mkdocs-glightbox==0.5.1 \
	mkdocs

DOCS_PORT ?= 8000

.PHONY: docs docs-build docs-clean

## Serve the docs with live reload on DOCS_PORT.
docs:
	$(MKDOCS) serve --dev-addr "127.0.0.1:$(DOCS_PORT)"

## Build once with --strict: fails on a broken link or a page missing from the nav.
docs-build:
	$(MKDOCS) build --strict

docs-clean:
	rm -rf .site

# ---- End-to-end tests (e2e/). `make e2e-setup` once: installs the package, Chromium and agent-browser's Chrome.
E2E = pnpm --dir e2e

.PHONY: e2e-setup e2e e2e-dev

e2e-setup:
	$(E2E) install
	$(E2E) exec playwright install chromium
	$(E2E) exec agent-browser install

## Full customer and agent flows against the compose stack (started if it is not running).
e2e:
	docker compose up -d --build --wait
	$(E2E) test

## Read-only smoke checks and the page-load SLA of the deployed develop hosts.
e2e-dev:
	$(E2E) test:smoke
	$(E2E) test:perf
