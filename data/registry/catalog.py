"""The lakehouse catalog: Iceberg tables in AWS Glue, with data and metadata in S3. The Glue databases
(one per namespace, `onboarding_<namespace>`) and the bucket come from infra/bootstrap.

Env (all optional):
- LAKEHOUSE_WAREHOUSE: s3:// prefix of the warehouse (default: the bucket from infra/bootstrap)
- LAKEHOUSE_AWS_PROFILE: AWS profile for Glue and S3 (default: aws-jhpark); LAKEHOUSE_AWS_REGION (ap-northeast-2)
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import boto3
from pyiceberg.catalog.glue import GlueCatalog

WAREHOUSE = os.environ.get("LAKEHOUSE_WAREHOUSE", "s3://onboarding-lakehouse-984171406552/warehouse")
REGION = os.environ.get("LAKEHOUSE_AWS_REGION", "ap-northeast-2")
PROFILE = os.environ.get("LAKEHOUSE_AWS_PROFILE", "aws-jhpark")


def data_root() -> Path:
    """$GWT_ROOT/.data, the local data directory shared by every worktree."""
    root = os.environ.get("GWT_ROOT")
    if not root:
        raise RuntimeError("GWT_ROOT is not set; run inside a worktree with direnv loaded")
    return Path(root) / ".data"


@cache
def catalog() -> GlueCatalog:
    # Glue gets the named profile (a profile-level endpoint_url elsewhere in ~/.aws/config must not
    # leak in); PyArrow's S3 FileIO only takes explicit keys, so they are resolved from the same profile.
    creds = boto3.Session(profile_name=PROFILE, region_name=REGION).get_credentials().get_frozen_credentials()
    props = {
        "warehouse": WAREHOUSE,
        "glue.profile-name": PROFILE,
        "glue.region": REGION,
        "s3.region": REGION,
        "s3.access-key-id": creds.access_key,
        "s3.secret-access-key": creds.secret_key,
    }
    if creds.token:
        props["s3.session-token"] = creds.token
    return GlueCatalog("lakehouse", **props)
