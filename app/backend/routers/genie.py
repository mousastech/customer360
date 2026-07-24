"""Genie Conversation API — OBO endpoints backing the floating chat widget.

All three calls run as the calling user (OBO) so Genie answers respect the user's
data permissions. The frontend polls get_message until a terminal status.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..auth import obo_client
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/genie", tags=["genie"])
_settings = get_settings()

_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


class AskBody(BaseModel):
    content: str


class ConversationStarted(BaseModel):
    conversation_id: str
    message_id: str


class MessageResult(BaseModel):
    status: str
    content: Optional[str] = None          # Genie's text answer
    query: Optional[str] = None            # generated SQL, if any
    columns: Optional[list[str]] = None    # result preview
    rows: Optional[list[list[Any]]] = None
    error: Optional[str] = None


@router.post("/conversations", response_model=ConversationStarted)
def start_conversation(body: AskBody, request: Request) -> ConversationStarted:
    genie = obo_client(request).genie
    wait = genie.start_conversation(space_id=_settings.genie_space_id, content=body.content)
    msg = wait.response
    return ConversationStarted(conversation_id=msg.conversation_id, message_id=msg.message_id)


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationStarted)
def create_message(conversation_id: str, body: AskBody, request: Request) -> ConversationStarted:
    genie = obo_client(request).genie
    wait = genie.create_message(
        space_id=_settings.genie_space_id, conversation_id=conversation_id, content=body.content
    )
    msg = wait.response
    return ConversationStarted(conversation_id=conversation_id, message_id=msg.message_id)


@router.get("/conversations/{conversation_id}/messages/{message_id}", response_model=MessageResult)
def get_message(conversation_id: str, message_id: str, request: Request) -> MessageResult:
    """Return current status; if terminal + has attachment, include result preview."""
    client = obo_client(request)
    genie = client.genie
    msg = genie.get_message(
        space_id=_settings.genie_space_id, conversation_id=conversation_id, message_id=message_id
    )
    status = msg.status.value if msg.status else "UNKNOWN"

    if status == "FAILED":
        return MessageResult(status=status, error=(msg.error.error if msg.error else "Genie failed"))
    if status not in _TERMINAL:
        return MessageResult(status=status)

    text: Optional[str] = None
    sql_query: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[list[Any]]] = None

    for att in msg.attachments or []:
        if att.text and att.text.content:
            text = att.text.content
        if att.query:
            sql_query = att.query.query
            try:
                res = genie.get_message_attachment_query_result(
                    space_id=_settings.genie_space_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    attachment_id=att.attachment_id,
                )
                columns, rows = _preview(res)
            except Exception as exc:  # noqa: BLE001 - preview is best-effort
                logger.warning("genie attachment result fetch failed: %s", exc)

    return MessageResult(
        status=status, content=text, query=sql_query, columns=columns, rows=rows
    )


def _preview(res, limit: int = 25) -> tuple[Optional[list[str]], Optional[list[list[Any]]]]:
    sr = getattr(res, "statement_response", None)
    if not sr or not sr.result or not sr.manifest or not sr.manifest.schema:
        return None, None
    cols = [c.name for c in sr.manifest.schema.columns]
    data = sr.result.data_array or []
    return cols, data[:limit]
