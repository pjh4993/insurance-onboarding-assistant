"""HTTP API (CONTRACTS.md §3): session links, customer endpoints (X-Session-Token), agent endpoints
(X-Agent-Id) and SSE streams."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from app.api.schemas import CreateSessionBody, InputBody, validate_data
from app.db.models import OnboardingSession
from app.services.pubsub import Broker, sse_frame
from app.services.runtime import InputError, Runtime

router = APIRouter()

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def broker(request: Request) -> Broker:
    return request.app.state.broker


RuntimeDep = Annotated[Runtime, Depends(runtime)]


async def customer_session(
    rt: RuntimeDep, x_session_token: Annotated[str | None, Header()] = None
) -> OnboardingSession:
    session = await rt.session_by_token(x_session_token or "")
    if session is None:
        raise HTTPException(401, "invalid or missing X-Session-Token")
    return session


def agent_id(x_agent_id: Annotated[str | None, Header()] = None) -> str:
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(401, "missing X-Agent-Id")
    return x_agent_id.strip()


async def agent_session(session_id: str, rt: RuntimeDep, _agent: Annotated[str, Depends(agent_id)]):
    session = await rt.get_session(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    return session


async def _accept_input(rt: Runtime, session: OnboardingSession, body: InputBody, actor: str) -> JSONResponse:
    try:
        data = validate_data(body.type, body.data)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False, include_context=False)) from exc
    try:
        await rt.submit_input(session, body.type, data, actor)
    except InputError as exc:
        raise HTTPException(exc.status, exc.detail) from exc
    return JSONResponse({"accepted": True}, status_code=202)


def _stream(request: Request, session_id: str | None, initial: list[str]) -> StreamingResponse:
    b: Broker = request.app.state.broker
    ping = request.app.state.settings.sse_ping_seconds
    return StreamingResponse(b.stream(session_id, ping, initial), media_type="text/event-stream", headers=SSE_HEADERS)


# ------------------------------------------------------------------------------------ public


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/sessions", status_code=201)
async def create_session(body: CreateSessionBody, rt: RuntimeDep) -> dict[str, Any]:
    session, token = await rt.create_session(body.market)
    return {"session_id": str(session.session_id), "token": token, "customer_path": f"/s/{token}"}


# ------------------------------------------------------------------------------------ customer


@router.get("/api/customer/session")
async def customer_get(rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(customer_session)]):
    return await rt.session_view(session)


@router.post("/api/customer/session/input", status_code=202)
async def customer_input(
    body: InputBody, rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(customer_session)]
):
    if body.type == "AGENT":
        raise HTTPException(403, "AGENT input is for agents only")
    return await _accept_input(rt, session, body, "CUSTOMER")


@router.get("/api/customer/session/stream")
async def customer_stream(
    request: Request, rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(customer_session)]
):
    view = await rt.session_view(session)
    return _stream(request, str(session.session_id), [sse_frame("session.updated", {"session": view["session"]})])


# ------------------------------------------------------------------------------------ agent


@router.get("/api/agent/sessions")
async def agent_list(rt: RuntimeDep, _agent: Annotated[str, Depends(agent_id)]):
    return {"sessions": await rt.list_summaries()}


@router.get("/api/agent/stream")
async def agent_stream_all(request: Request, _agent: Annotated[str, Depends(agent_id)]):
    return _stream(request, None, [])


@router.get("/api/agent/sessions/{session_id}")
async def agent_detail(rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(agent_session)]):
    return await rt.session_detail(session)


@router.post("/api/agent/sessions/{session_id}/assign")
async def agent_assign(
    rt: RuntimeDep,
    session: Annotated[OnboardingSession, Depends(agent_session)],
    agent: Annotated[str, Depends(agent_id)],
):
    updated = await rt.assign(str(session.session_id), agent)
    view = await rt.session_view(updated)
    return view["session"]


@router.post("/api/agent/sessions/{session_id}/input", status_code=202)
async def agent_input(body: InputBody, rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(agent_session)]):
    return await _accept_input(rt, session, body, "AGENT")


@router.get("/api/agent/sessions/{session_id}/stream")
async def agent_stream_one(
    request: Request, rt: RuntimeDep, session: Annotated[OnboardingSession, Depends(agent_session)]
):
    view = await rt.session_view(session)
    return _stream(request, str(session.session_id), [sse_frame("session.updated", {"session": view["session"]})])
