"""Operator API (CONTRACTS.md §3): the agent config versions behind the operator console. The frontend
verifies the operator's Cognito login (the `operators` group) and sends X-Operator-Id; the backend is reachable
only from the frontend, as with X-Agent-Id."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.operator import OperatorConsole, OperatorError

router = APIRouter(prefix="/api/operator")


def console(request: Request) -> OperatorConsole:
    return request.app.state.operator


def operator_id(x_operator_id: Annotated[str | None, Header()] = None) -> str:
    if not x_operator_id or not x_operator_id.strip():
        raise HTTPException(401, "missing X-Operator-Id")
    return x_operator_id.strip()


ConsoleDep = Annotated[OperatorConsole, Depends(console)]
OperatorDep = Annotated[str, Depends(operator_id)]


class DraftBody(BaseModel):
    files: dict[str, str] = Field(description="relative path -> file content: config.json and flows/<name>.json")


class PublishBody(DraftBody):
    notes: str = Field("", max_length=2000)
    bump: Literal["patch", "minor"] = "patch"


async def run(fn, *args, **kwargs) -> Any:
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except OperatorError as exc:
        raise HTTPException(exc.status, {"message": exc.detail, "problems": exc.problems}) from exc


@router.get("/config")
async def config_status(op: ConsoleDep, _who: OperatorDep) -> dict[str, Any]:
    """Which version the backend runs (live), which one a restart would load (next), what can be done here."""
    return await run(op.status)


@router.get("/config/versions")
async def config_versions(op: ConsoleDep, _who: OperatorDep) -> dict[str, Any]:
    return {"versions": await run(op.versions)}


@router.get("/config/versions/{version}")
async def config_version(version: str, op: ConsoleDep, _who: OperatorDep) -> dict[str, Any]:
    return await run(op.version, version)


@router.post("/config/validate")
async def config_validate(body: DraftBody, op: ConsoleDep, _who: OperatorDep) -> dict[str, Any]:
    return await run(op.validate, body.files)


@router.post("/config/versions", status_code=201)
async def config_publish(body: PublishBody, op: ConsoleDep, who: OperatorDep) -> dict[str, Any]:
    return await run(op.publish, body.files, operator=who, notes=body.notes, bump=body.bump)


@router.post("/restart", status_code=202)
async def restart(op: ConsoleDep, who: OperatorDep) -> dict[str, Any]:
    return await run(op.restart, operator=who)
