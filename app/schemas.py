"""
Pydantic schemas matching the assignment's exact API contract.
The schema is non-negotiable — deviating breaks the automated evaluator.
"""
from typing import List, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(
        ...,
        min_length=1,
        description="Full conversation history, oldest message first.",
    )


class Recommendation(BaseModel):
    name: str = Field(..., description="Exact assessment name from the SHL catalog.")
    url: str  = Field(..., description="Canonical SHL catalog URL for this assessment.")
    test_type: str = Field(..., description="Test type code(s): A/B/C/D/E/K/P/S.")


class ChatResponse(BaseModel):
    reply: str = Field(
        ...,
        description="Agent's natural language response to the user.",
    )
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description=(
            "Empty when clarifying or refusing. "
            "1–10 items when the agent has committed to a shortlist."
        ),
    )
    end_of_conversation: bool = Field(
        default=False,
        description="True only when the agent considers the task complete.",
    )
