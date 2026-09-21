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
