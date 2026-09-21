"""MkDocs build hooks. In a dot-directory so the site build does not collect it."""

import os

from mkdocs.structure.files import File

NAV_CONFIG = ".nav.yml"
WATCHED = ("docs", "contracts")
DOCS_PREFIX = "docs/"


def on_files(files, config):
    """Restore the root `.nav.yml` (`same-dir` drops it), then publish docs/ at the site root.

    The site is built from the repo root so links read the same on GitHub, but served under /docs, so pages
    under docs/ would otherwise land at /docs/docs/…. docs/README.md becomes the front page and the repo
    README moves to overview/. MkDocs builds every link from these URLs, so links and assets follow.
    """
    if files.get_file_from_path(NAV_CONFIG) is None and os.path.isfile(os.path.join(config.docs_dir, NAV_CONFIG)):
        files.append(File(NAV_CONFIG, config.docs_dir, config.site_dir, use_directory_urls=config.use_directory_urls))
    for file in files:
        if file.src_uri == "README.md":
            _move(file, "overview/index.html" if config.use_directory_urls else "overview.html")
        elif file.src_uri == "CONTRACTS.md":  # lowercase, next to contracts/seed-customers.json
            _move(file, "contracts/index.html" if config.use_directory_urls else "contracts.html")
        elif file.src_uri.startswith(DOCS_PREFIX):
            _move(file, file.dest_uri.removeprefix(DOCS_PREFIX))
    return files


def _move(file: File, dest_uri: str) -> None:
    file.dest_uri = dest_uri
    file.url = "" if dest_uri == "index.html" else dest_uri.removesuffix("index.html")
    file.abs_dest_path = os.path.normpath(os.path.join(file.dest_dir, dest_uri))


def on_serve(server, config, builder):
    """Watch only site content: `serve` otherwise rebuilds on every change under the repo (node_modules, .venv, …)."""
    root = config.docs_dir
    server.unwatch(root)
    server.watch(root, recursive=False)  # README.md, CONTRACTS.md, .nav.yml
    for name in WATCHED:
        server.watch(os.path.join(root, name))
    return server
