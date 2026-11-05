"""Typed data models and schema definitions for Real Estate Intelligence."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ProjectRecord:
    project_id: int
    name: str
    registration_number: str
    promoter_id: int
    promoter_name: str
    district: str
    taluka: Optional[str] = None
    project_type: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    total_units: Optional[int] = None
    booked_units: Optional[int] = None
    unbooked_units: Optional[int] = None
    booking_rate_pct: Optional[float] = None
    latest_form_one_progress_pct: Optional[float] = None
    estimated_cost_inr: Optional[float] = None
    incurred_cost_inr: Optional[float] = None
    collection_status: str = "complete"
    # Land & Spatial coordinates
    tp_scheme: Optional[str] = None
    final_plot_no: Optional[str] = None
    survey_no: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_url: Optional[str] = None
    # Legal Handover & Milestones
    society_reg_date: Optional[str] = None
    form_four_status: Optional[str] = None
    bu_status: Optional[str] = None
    # Construction Velocity Analytics
    time_elapsed_pct: Optional[float] = None
    engg_score_pct: Optional[float] = None
    arch_score_pct: Optional[float] = None
    velocity_ratio: Optional[float] = None
    progress_status_label: Optional[str] = None
    # Regulatory & Litigation Radar
    has_complaints: int = 0
    complaints_count: int = 0
    has_alterations: int = 0
    alterations_count: int = 0
    has_extensions: int = 0
    extensions_count: int = 0
    default_quarters_count: int = 0


@dataclass
class PromoterRecord:
    promoter_id: int
    name: str
    promoter_type: Optional[str] = None
    total_projects_claimed: Optional[int] = None
    completed_projects_claimed: Optional[int] = None
    ongoing_projects_claimed: Optional[int] = None
    linked_gujrera_projects_count: int = 0


@dataclass
class ProfessionalRecord:
    project_id: int
    role: str  # 'architect', 'engineer', 'ca', 'contractor'
    name: str
    firm_name: Optional[str] = None
    license_or_reg_no: Optional[str] = None


@dataclass
class BankRecord:
    project_id: int
    bank_name: str
    branch_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_type: Optional[int] = 1  # 1 = Retention/Escrow, 2 = Collection
    account_name: Optional[str] = None
    account_number_masked: Optional[str] = None
    deposit_amt: Optional[float] = None
    withdrawal_amt: Optional[float] = None
    opening_bal: Optional[float] = None
    closing_bal: Optional[float] = None
    opening_date: Optional[str] = None
    closing_date: Optional[str] = None
    passbook_id: Optional[str] = None


@dataclass
class QuarterlyProgressRecord:
    project_id: int
    quarter_name: str
    period_label: Optional[str] = None
    progress_percentage: float = 0.0
    submission_date: Optional[str] = None
    form_one_id: Optional[int] = None
    form_two_id: Optional[int] = None
    form_three_id: Optional[int] = None


@dataclass
class InventoryBlockRecord:
    project_id: int
    block_name: str
    total_units: int
    booked_units: int
    unbooked_units: int
    booking_rate_pct: float
    residential_units: int = 0
    commercial_units: int = 0


@dataclass
class FinancialRecord:
    project_id: int
    filing_date: str
    filing_type: str  # 'index' or 'latest'
    form_three_id: int
    estimated_cost: Optional[float] = None
    incurred_and_paid: Optional[float] = None
    booked_consideration: Optional[float] = None
    received_amount: Optional[float] = None
    balance_amount: Optional[float] = None
    unbooked_consideration: Optional[float] = None
    total_residential: int = 0
    total_commercial_shop: int = 0
    total_commercial_office: int = 0
    loan_rows_count: int = 0


@dataclass
class FormFiveRecord:
    project_id: int
    financial_year: str
    status: str
    submitted_on: Optional[str] = None
    doc_uid: Optional[str] = None


@dataclass
class NocBuRecord:
    project_id: int
    block_name: str
    bu_check: Optional[str] = None
    bu_date: Optional[str] = None
    fire_doc_id: Optional[str] = None
    lift_doc_id: Optional[str] = None


@dataclass
class UnitTransactionRecord:
    project_id: int
    block_name: str
    unit_type: Optional[str] = None
    carpet_area_sqm: float = 0.0
    carpet_area_sqft: float = 0.0
    unit_consideration: float = 0.0
    rate_per_sqft: Optional[float] = None
    rate_per_sqm: Optional[float] = None
    status: str = "UNBOOKED"
    agreement_date: Optional[str] = None
    form_three_id: Optional[int] = None


@dataclass
class DiscrepancyLead:
    project_id: int
    category: str  # 'financial', 'schedule', 'inventory', 'statutory', 'regulatory'
    severity: str  # 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    title: str
    detail: str
    evidence_source: str
    reconciliation_guidance: str


@dataclass
class DossierReport:
    project: ProjectRecord
    promoter: PromoterRecord
    professionals: List[ProfessionalRecord] = field(default_factory=list)
    banks: List[BankRecord] = field(default_factory=list)
    blocks: List[InventoryBlockRecord] = field(default_factory=list)
    progress_timeline: List[QuarterlyProgressRecord] = field(default_factory=list)
    finances: List[FinancialRecord] = field(default_factory=list)
    compliance_history: List[FormFiveRecord] = field(default_factory=list)
    bu_records: List[NocBuRecord] = field(default_factory=list)
    leads: List[DiscrepancyLead] = field(default_factory=list)
    evidence_hashes: List[dict] = field(default_factory=list)
