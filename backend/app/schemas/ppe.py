from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.ppe_catalog import KKD_KATEGORILERI, STATUS_LABELS


class PpeAssignmentCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    employee_id: int
    inventory_item_id: int | None = None
    delivery_date: date
    category: str = Field(min_length=2, max_length=120)
    item_type: str = Field(min_length=2, max_length=160)
    quantity: int = Field(default=1, ge=1, le=9999)
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=60)
    serial_no: str | None = Field(default=None, max_length=120)
    shelf_life_text: str | None = Field(default=None, max_length=120)
    expiry_date: date | None = None
    warranty_text: str | None = Field(default=None, max_length=120)
    renewal_date: date | None = None
    status: str = Field(default="teslim", max_length=40)
    delivered_by: str | None = Field(default=None, max_length=160)
    risk_note: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_catalog(self):
        if self.category not in KKD_KATEGORILERI:
            raise ValueError("Geçersiz KKD kategorisi.")
        types = KKD_KATEGORILERI[self.category]
        if self.item_type not in types and self.category != "Diğer":
            raise ValueError("Seçilen kategori için geçersiz KKD türü.")
        if self.status not in STATUS_LABELS:
            raise ValueError("Geçersiz KKD durumu.")
        return self


class PpeAssignmentUpdate(BaseModel):
    delivery_date: date | None = None
    category: str | None = Field(default=None, max_length=120)
    item_type: str | None = Field(default=None, max_length=160)
    quantity: int | None = Field(default=None, ge=1, le=9999)
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=60)
    serial_no: str | None = Field(default=None, max_length=120)
    shelf_life_text: str | None = Field(default=None, max_length=120)
    expiry_date: date | None = None
    warranty_text: str | None = Field(default=None, max_length=120)
    renewal_date: date | None = None
    status: str | None = Field(default=None, max_length=40)
    delivered_by: str | None = Field(default=None, max_length=160)
    risk_note: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    branch_id: int | None = None


class PpePhotoResponse(BaseModel):
    id: int
    assignment_id: int
    original_name: str | None
    content_type: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PpeAssignmentResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None
    employee_id: int
    inventory_item_id: int | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    employee_job_title: str | None = None
    delivery_date: date
    category: str
    item_type: str
    quantity: int
    brand: str | None
    model: str | None
    size: str | None
    serial_no: str | None
    shelf_life_text: str | None
    expiry_date: date | None
    warranty_text: str | None
    renewal_date: date | None
    status: str
    status_label: str
    returned_quantity: int = 0
    scrapped_quantity: int = 0
    remaining_quantity: int = 0
    delivered_by: str | None
    risk_note: str | None
    notes: str | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    photos: list[PpePhotoResponse] = []
    model_config = ConfigDict(from_attributes=True)


class PpeDueSummary(BaseModel):
    overdue: int
    due_soon: int
    total_active: int
    low_stock: int = 0
    stock_overdue: int = 0
    stock_due_soon: int = 0


class PpeInventoryCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    category: str = Field(min_length=2, max_length=120)
    item_type: str = Field(min_length=2, max_length=160)
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=60)
    shelf_life_text: str | None = Field(default=None, max_length=120)
    expiry_date: date | None = None
    renewal_date: date | None = None
    min_stock: int = Field(default=0, ge=0, le=999999)
    initial_quantity: int = Field(default=0, ge=0, le=999999)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_catalog(self):
        if self.category not in KKD_KATEGORILERI:
            raise ValueError("Geçersiz KKD kategorisi.")
        types = KKD_KATEGORILERI[self.category]
        if self.item_type not in types and self.category != "Diğer":
            raise ValueError("Seçilen kategori için geçersiz KKD türü.")
        return self


class PpeInventoryMovementCreate(BaseModel):
    # Zimmet ve iade hareketleri, ilgili zimmet uçlarından otomatik yazılır.
    # Dışarıdan yalnızca depoya giriş ve depodaki fire kaydı açılabilir.
    movement_type: Literal["inbound", "scrap"]
    quantity: int = Field(ge=1, le=999999)
    movement_date: date = Field(default_factory=date.today)
    reason: str | None = Field(default=None, max_length=500)


class PpeInventoryMovementResponse(BaseModel):
    id: int
    company_id: int
    inventory_item_id: int
    assignment_id: int | None
    movement_type: str
    quantity: int
    movement_date: date
    reason: str | None
    created_by_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PpeInventoryResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None
    category: str
    item_type: str
    brand: str | None
    model: str | None
    size: str | None
    shelf_life_text: str | None
    expiry_date: date | None
    renewal_date: date | None
    min_stock: int
    notes: str | None
    is_active: bool
    received_quantity: int = 0
    issued_quantity: int = 0
    returned_quantity: int = 0
    scrapped_quantity: int = 0
    available_quantity: int = 0
    stock_state: str = "ok"
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PpeAssignmentAction(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=999999)
    movement_date: date = Field(default_factory=date.today)
    reason: str | None = Field(default=None, max_length=500)
