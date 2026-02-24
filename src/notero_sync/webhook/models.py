"""Pydantic models for Notion webhook payloads."""

from pydantic import BaseModel


class WebhookEvent(BaseModel):
    """A single event from a Notion webhook payload."""

    type: str  # e.g. "page.properties_updated", "page.content_updated"
    id: str  # unique event ID
    data: dict  # contains page_id and other details


class WebhookPayload(BaseModel):
    """Top-level Notion webhook payload.

    Notion may send:
    - A verification request (with verification_token)
    - Event notifications (with events list)
    """

    verification_token: str | None = None
    events: list[WebhookEvent] | None = None
