from aegis_review.adapters.base import RepositorySnapshot
from aegis_review.adapters.registry import default_registry
from aegis_review.planning import build_review_plan


def test_sensitive_angular_change_selects_security_and_frontend_teams() -> None:
    files = ["src/app/auth/access-policy.component.ts"]
    snapshot = RepositorySnapshot(
        changed_files=tuple(files),
        manifests={"package.json": '{"dependencies":{"@angular/core":"20"}}'},
    )

    plan = build_review_plan(files, default_registry().detect(snapshot))
    leads = {assignment.lead_agent for assignment in plan.assignments}

    assert {"correctness", "security", "frontend", "testing"} <= leads
    assert plan.risk_level == "high"


def test_test_only_change_does_not_add_test_coverage_team() -> None:
    files = ["tests/test_parser.py", "src/parser.spec.ts"]

    plan = build_review_plan(files, [])
    leads = {assignment.lead_agent for assignment in plan.assignments}

    assert "correctness" in leads
    assert "testing" not in leads

