"""Training data Pydantic schemas — preview, export, and cost estimation responses."""

from pydantic import BaseModel, Field


class TrainingSampleResponse(BaseModel):
    """A single instruction-tuning training sample."""

    instruction: str = Field(..., description="System or user instruction")
    input: str = Field(..., description="Context or document text")
    output: str = Field(..., description="Expected model response")
    domain: str = Field(default="domain", description="Domain tag")
    type: str = Field(default="qa", description="Sample type: qa, summary, reasoning, general")


class TrainingDataPreviewResponse(BaseModel):
    """Preview of the instruction-tuning dataset (metadata + first N samples)."""

    dataset_id: str
    dataset_version: int
    total_samples: int
    domain_samples: int
    general_samples: int
    by_type: dict[str, int] = Field(default_factory=dict)
    preview_samples: list[TrainingSampleResponse] = Field(
        default_factory=list,
        description="First 10 samples for preview",
    )


class TrainingDataExportResponse(BaseModel):
    """Full export of the instruction-tuning dataset."""

    dataset_id: str
    dataset_version: int
    total_samples: int
    domain_samples: int
    general_samples: int
    by_type: dict[str, int] = Field(default_factory=dict)
    samples: list[TrainingSampleResponse]


class CostEstimateResponse(BaseModel):
    """Cost estimation for a fine-tuning job (pre-flight check)."""

    model_id: str
    estimated_cost: float = Field(..., description="Estimated cost in USD")
    estimated_time_min: int = Field(..., description="Estimated training time in minutes")
    dataset_sample_count: int = Field(..., description="Number of training samples")
    remaining_budget: float = Field(..., description="Remaining monthly budget in USD")
    within_budget: bool = Field(..., description="Whether the job fits within the budget")
