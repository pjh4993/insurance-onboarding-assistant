"""The lakehouse catalog: Iceberg tables whose data and metadata live in S3, tracked by a SQLite
catalog on this machine.

Env (all optional):
- LAKEHOUSE_WAREHOUSE: s3:// prefix of the warehouse (default: the bucket from infra/bootstrap)
- LAKEHOUSE_CATALOG_URI: SQLAlchemy URL of the catalog DB (default: $GWT_ROOT/.data/lakehouse/catalog.db)
- LAKEHOUSE_AWS_PROFILE: AWS profile for S3 (default: aws-jhpark); LAKEHOUSE_AWS_REGION (ap-northeast-2)
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import boto3
from pyiceberg.catalog.sql import SqlCatalog

WAREHOUSE = os.environ.get("LAKEHOUSE_WAREHOUSE", "s3://onboarding-lakehouse-984171406552/warehouse")
REGION = os.environ.get("LAKEHOUSE_AWS_REGION", "ap-northeast-2")
PROFILE = os.environ.get("LAKEHOUSE_AWS_PROFILE", "aws-jhpark")


def data_root() -> Path:
    """$GWT_ROOT/.data, the local data directory shared by every worktree."""
    root = os.environ.get("GWT_ROOT")
    if not root:
        raise RuntimeError("GWT_ROOT is not set; run inside a worktree with direnv loaded")
    return Path(root) / ".data"


def _catalog_uri() -> str:
    uri = os.environ.get("LAKEHOUSE_CATALOG_URI")
    if uri:
        return uri
    path = data_root() / "lakehouse" / "catalog.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


@cache
def catalog() -> SqlCatalog:
    creds = boto3.Session(profile_name=PROFILE, region_name=REGION).get_credentials().get_frozen_credentials()
    props = {
        "uri": _catalog_uri(),
        "warehouse": WAREHOUSE,
        "s3.region": REGION,
        "s3.access-key-id": creds.access_key,
        "s3.secret-access-key": creds.secret_key,
    }
    if creds.token:
        props["s3.session-token"] = creds.token
    return SqlCatalog("lakehouse", **props)
