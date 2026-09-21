"""MkDocs build hooks. In a dot-directory so the site build does not collect it."""

import os

from mkdocs.structure.files import File

NAV_CONFIG = ".nav.yml"
WATCHED = ("docs", "contracts")


def on_files(files, config):
    """Restore the root `.nav.yml`: `same-dir` drops every non-document file at the root, this one included."""
    if files.get_file_from_path(NAV_CONFIG) is None and os.path.isfile(os.path.join(config.docs_dir, NAV_CONFIG)):
        files.append(File(NAV_CONFIG, config.docs_dir, config.site_dir, use_directory_urls=config.use_directory_urls))
    return files


def on_serve(server, config, builder):
    """Watch only site content: `serve` otherwise rebuilds on every change under the repo (node_modules, .venv, …)."""
    root = config.docs_dir
    server.unwatch(root)
    server.watch(root, recursive=False)  # README.md, CONTRACTS.md, .nav.yml
    for name in WATCHED:
        server.watch(os.path.join(root, name))
    return server
