"""Pydantic response/request models — enforce shape and document OpenAPI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class CustomerListItem(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    email: str
    country: Optional[str] = None
    segment_id: Optional[str] = None
    lifetime_value: float = 0.0
    churn_score: float = 0.0


class Page(BaseModel):
    items: list[CustomerListItem]
    total: int
    page: int
    page_size: int


class Transaction(BaseModel):
    transaction_id: str
    product_id: Optional[str] = None
    transaction_date: Optional[date] = None
    channel: Optional[str] = None
    status: Optional[str] = None
    amount: float = 0.0


class CustomerProfile(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    signup_date: Optional[date] = None
    last_purchase_date: Optional[date] = None
    segment_id: Optional[str] = None
    lifetime_value: float = 0.0
    churn_score: float = 0.0
    updated_at: Optional[datetime] = None


class CustomerDetail(BaseModel):
    profile: CustomerProfile
    transactions: list[Transaction]


class CategorySpend(BaseModel):
    category: str
    total: float


class CustomerMetrics(BaseModel):
    lifetime_spend: float = 0.0
    top_categories: list[CategorySpend] = Field(default_factory=list)
    last_30d: float = 0.0
    last_90d: float = 0.0
    open_tickets: int = 0
    avg_csat: Optional[float] = None


class Note(BaseModel):
    id: int
    customer_id: str
    note: str
    author_email: str
    created_at: datetime
    processed: bool


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=4000)


class NoteCreated(BaseModel):
    id: int
    created_at: datetime


class SegmentOverride(BaseModel):
    customer_id: str
    segment_id: str
    author_email: str
    updated_at: datetime
    processed: bool


class SegmentOverrideCreate(BaseModel):
    segment_id: str = Field(min_length=1, max_length=16)


class Segment(BaseModel):
    segment_id: str
    segment_name: str
    description: Optional[str] = None


class AppConfig(BaseModel):
    databricks_host: str
    dashboard_id: str
    genie_space_id: str
    workspace_id: Optional[str] = None
    user_email: Optional[str] = None
