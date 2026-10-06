from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class TemplateId(StrEnum):
    RECT_PLATE = "rectangular_plate"
    ROUND_PLATE = "circular_plate"
    L_BRACKET = "l_bracket"
    U_CHANNEL = "u_channel"
    Z_BRACKET = "z_bracket"


class DisplayUnits(StrEnum):
    MM = "mm"
    IN = "in"


class PartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    template_id: TemplateId
    recipe_version: Literal["0.1.0"] = "0.1.0"
    material: Literal["5052-H32 aluminum"] = "5052-H32 aluminum"
    stock_thickness_mm: float = Field(default=1.6002, gt=0)
    supplier_profile_id: Literal["sendcutsend-5052-h32-0.063in"] = "sendcutsend-5052-h32-0.063in"
    supplier_profile_version: int = Field(default=1, ge=1)
    quantity: int = Field(default=1, ge=1, le=10000)
    revision: int = Field(default=1, ge=1)
    parameters: dict[str, float] = Field(default_factory=dict)
    holes: list[dict[str, float]] = Field(default_factory=list)
    slots: list[dict[str, float]] = Field(default_factory=list)
    cutouts: list[dict[str, float]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confirmed_requirements: list[str] = Field(default_factory=list)


class DraftSpec(BaseModel):
    proposal: PartSpec | None = None
    questions: list[str] = Field(default_factory=list)
    explanation: str
    based_on_revision: int = Field(ge=1)


class DesignProposal(BaseModel):
    message: str
    questions: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    spec: PartSpec | None = None
    based_on_revision: int = Field(ge=1)


class Finding(BaseModel):
    id: str
    severity: Literal["pass", "warning", "error", "unknown"]
    title: str
    detail: str
    feature_id: str | None = None


class InspectionFeature(BaseModel):
    id: str
    kind: str
    label: str
    dimensions: dict[str, float | str] = Field(default_factory=dict)
    point_mm: list[float] | None = None


class BuildResult(BaseModel):
    revision: int
    geometry_status: Literal["valid", "invalid"]
    supplier_status: Literal["passed", "incomplete", "failed"]
    evidence_status: Literal["experimental", "validated"] = "experimental"
    findings: list[Finding] = Field(default_factory=list)
    features: list[InspectionFeature] = Field(default_factory=list)
    bounds_mm: dict[str, float] = Field(default_factory=dict)
    glb_url: str
    export_url: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revision: int = 1
    display_units: DisplayUnits = DisplayUnits.MM
    spec: PartSpec
    conversation: list[dict[str, str]] = Field(default_factory=list)
    build: BuildResult | None = None
