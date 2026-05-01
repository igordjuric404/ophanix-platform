"""Organization and environment scoping helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Request
from pydantic import BaseModel


class Organization(BaseModel):
    """Product organization."""

    id: str
    name: str
    slug: str
    created_at: str


class Environment(BaseModel):
    """Product environment within an organization."""

    id: str
    organization_id: str
    name: str
    slug: str
    type: str
    created_at: str


class EnvironmentCreateRequest(BaseModel):
    """Create an environment in the selected organization."""

    name: str
    slug: str
    type: str = "development"


class TenantStore:
    """In-memory tenant store used until the canonical DB phase."""

    def __init__(
        self,
        organizations: list[Organization] | None = None,
        environments: list[Environment] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._organizations = {
            organization.id: organization
            for organization in (
                organizations
                or [
                    Organization(
                        id="org_default",
                        name="Ophanix Demo",
                        slug="ophanix-demo",
                        created_at=now,
                    )
                ]
            )
        }
        self._environments = {
            environment.id: environment
            for environment in (
                environments
                or [
                    Environment(
                        id="env_default",
                        organization_id="org_default",
                        name="Development",
                        slug="development",
                        type="development",
                        created_at=now,
                    )
                ]
            )
        }

    def get_organization(self, organization_id: str) -> Organization | None:
        return self._organizations.get(organization_id)

    def list_organizations(self, organization_ids: list[str]) -> list[Organization]:
        return [
            organization
            for organization_id in organization_ids
            if (organization := self._organizations.get(organization_id)) is not None
        ]

    def get_environment(self, environment_id: str) -> Environment | None:
        return self._environments.get(environment_id)

    def list_environments(self, organization_id: str) -> list[Environment]:
        return [
            environment
            for environment in self._environments.values()
            if environment.organization_id == organization_id
        ]

    def create_environment(
        self,
        *,
        organization_id: str,
        name: str,
        slug: str,
        environment_type: str,
    ) -> Environment:
        environment = Environment(
            id=f"env_{slug.replace('-', '_')}",
            organization_id=organization_id,
            name=name,
            slug=slug,
            type=environment_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._environments[environment.id] = environment
        return environment


def apply_organization_scope(filters: dict[str, str], organization_id: str) -> dict[str, str]:
    """Return query filters with the organization scope enforced."""

    scoped = dict(filters)
    scoped["organization_id"] = organization_id
    return scoped


def require_environment_context(request: Request) -> str:
    """Require an environment selection for environment-scoped resources."""

    environment_id = getattr(request.state, "selected_environment_id", None)
    if not environment_id:
        raise HTTPException(status_code=400, detail="X-Environment-ID is required.")
    return str(environment_id)
