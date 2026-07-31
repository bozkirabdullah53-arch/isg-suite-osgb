from pydantic import BaseModel, ConfigDict, Field
class BranchCreate(BaseModel):
    company_id: int
    name: str = Field(min_length=2, max_length=160)
    sgk_registry_no: str | None = None
    city: str | None = None
    address: str | None = None
class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    sgk_registry_no: str | None = None
    city: str | None = None
    address: str | None = None
    is_active: bool | None = None
class BranchResponse(BranchCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
