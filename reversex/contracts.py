"""Validate every action proposed by a model before touching the browser."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Action(str, Enum):
    OBSERVE = "observe"
    CLICK = "click"
    FILL = "fill"
    RELOAD = "reload"
    STOP = "stop"


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    element_id: str | None = Field(default=None, max_length=40)
    value: str | None = Field(default=None, max_length=200)
    reason: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def check_consistency(self):
        if self.action in (Action.CLICK, Action.FILL) and self.element_id is None:
            raise ValueError("click/fill require an element_id")
        if self.action == Action.FILL and self.value is None:
            raise ValueError("fill requires a value (empty string is allowed)")
        if self.action != Action.FILL and self.value is not None:
            raise ValueError("value may only be supplied for fill")
        if self.action not in (Action.CLICK, Action.FILL) and self.element_id is not None:
            raise ValueError("element_id may only be supplied for click/fill")
        return self


class VisibleElement(BaseModel):
    """Structured control observation. Extra fields are optional for backward compatibility."""

    model_config = ConfigDict(extra="ignore")

    element_id: str
    kind: str
    label: str
    value: str | None = None
    placeholder: str | None = None
    role: str | None = None
    input_type: str | None = None
    disabled: bool = False
    readonly: bool = False
    checked: bool | None = None
    selected: str | None = None
    href: str | None = None
    value_redacted: bool = False


class ControlValueChange(BaseModel):
    """Observable before/after difference for a form control — no causal claims."""

    model_config = ConfigDict(extra="forbid")

    element_id_after: str | None = None
    kind: str
    label: str
    field: str
    before: str | None = None
    after: str | None = None


class PageSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    snapshot_id: int
    url: str
    title: str
    visible_text: str
    elements: list[VisibleElement]
    # Optional delta vs prior snapshot (filled by SafeBrowser.act when applicable).
    control_changes: list[ControlValueChange] = Field(default_factory=list)


class StepResult(BaseModel):
    decision: Decision
    status: str
    detail: str
    snapshot: PageSnapshot | None = None
