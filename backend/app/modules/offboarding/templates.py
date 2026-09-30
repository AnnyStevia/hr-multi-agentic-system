"""In-code default checklist / clearance templates (no DB template admin)."""

from dataclasses import dataclass

from app.modules.offboarding.models import (
    OffboardingClearanceCategory,
    OffboardingTaskCategory,
)


@dataclass(frozen=True)
class OffboardingTaskTemplate:
    title: str
    description: str
    category: OffboardingTaskCategory
    is_required: bool = True


@dataclass(frozen=True)
class OffboardingClearanceTemplate:
    item: str
    category: OffboardingClearanceCategory


DEFAULT_OFFBOARDING_TASK_TEMPLATES: tuple[OffboardingTaskTemplate, ...] = (
    OffboardingTaskTemplate(
        title="Verify offboarding documentation",
        description="Confirm required offboarding documents are identified and available.",
        category=OffboardingTaskCategory.DOCUMENTS,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Collect required documents",
        description="Collect signed or submitted documents needed for the offboarding file.",
        category=OffboardingTaskCategory.DOCUMENTS,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Complete work and knowledge handover",
        description="Ensure ongoing work, credentials handoff notes, and knowledge transfer are documented.",
        category=OffboardingTaskCategory.HANDOVER,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Return laptop",
        description="Collect the company laptop and record condition / asset details.",
        category=OffboardingTaskCategory.EQUIPMENT,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Return badge/access card",
        description="Collect badge or physical access card.",
        category=OffboardingTaskCategory.EQUIPMENT,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Return company equipment",
        description="Collect other company equipment (monitor, phone, peripherals, etc.).",
        category=OffboardingTaskCategory.EQUIPMENT,
        is_required=False,
    ),
    OffboardingTaskTemplate(
        title="Prepare system access revocation",
        description="Prepare revocation of application and account access (do not revoke in this phase).",
        category=OffboardingTaskCategory.ACCESS,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Prepare repository/VPN access revocation",
        description="Prepare revocation of repository and VPN access (do not revoke in this phase).",
        category=OffboardingTaskCategory.ACCESS,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Final HR verification",
        description="HR confirms offboarding checklist progress and file completeness.",
        category=OffboardingTaskCategory.ADMINISTRATION,
        is_required=True,
    ),
    OffboardingTaskTemplate(
        title="Final administrative verification",
        description="Administrative follow-up checks before clearance/finalization phases.",
        category=OffboardingTaskCategory.ADMINISTRATION,
        is_required=True,
    ),
)

DEFAULT_OFFBOARDING_CLEARANCE_TEMPLATES: tuple[OffboardingClearanceTemplate, ...] = (
    OffboardingClearanceTemplate(item="Laptop", category=OffboardingClearanceCategory.EQUIPMENT),
    OffboardingClearanceTemplate(
        item="Badge / access card", category=OffboardingClearanceCategory.EQUIPMENT
    ),
    OffboardingClearanceTemplate(
        item="Company phone", category=OffboardingClearanceCategory.EQUIPMENT
    ),
    OffboardingClearanceTemplate(
        item="Other company equipment", category=OffboardingClearanceCategory.EQUIPMENT
    ),
    OffboardingClearanceTemplate(item="Email", category=OffboardingClearanceCategory.ACCESS),
    OffboardingClearanceTemplate(item="VPN", category=OffboardingClearanceCategory.ACCESS),
    OffboardingClearanceTemplate(
        item="GitHub / repositories", category=OffboardingClearanceCategory.ACCESS
    ),
    OffboardingClearanceTemplate(
        item="Internal applications", category=OffboardingClearanceCategory.ACCESS
    ),
    OffboardingClearanceTemplate(item="Other systems", category=OffboardingClearanceCategory.ACCESS),
)
