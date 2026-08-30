import pytest

from aegis_review.adapters.base import RepositorySnapshot, SignalAdapter
from aegis_review.adapters.registry import AdapterRegistry, default_registry


def test_angular_typescript_repository_uses_composable_adapters() -> None:
    snapshot = RepositorySnapshot(
        changed_files=("src/app/users/users.component.ts", "angular.json"),
        manifests={
            "package.json": '{"dependencies":{"@angular/core":"20.0.0","typescript":"5.8"}}'
        },
    )

    names = {match.name for match in default_registry().detect(snapshot)}

    assert {"angular", "typescript", "javascript"} <= names


def test_react_typescript_repository_uses_both_framework_and_language() -> None:
    snapshot = RepositorySnapshot(
        changed_files=("src/Cart.tsx",),
        manifests={"package.json": '{"dependencies":{"react":"19.0.0","typescript":"5.8"}}'},
    )

    names = {match.name for match in default_registry().detect(snapshot)}

    assert {"react", "typescript"} <= names


def test_registry_rejects_duplicate_adapter_names() -> None:
    adapter = SignalAdapter(name="example", kind="language", extensions=(".example",))
    registry = AdapterRegistry([adapter])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(adapter)

