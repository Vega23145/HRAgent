from __future__ import annotations

from resumehub.app.core import db
from resumehub.app.core.plugin import AdminResource, AppContext, Module

from .bootstrap import ensure_defaults
from .router import router


class UsersModule(Module):
    name = "users"
    prefix = ""  # serves /users, /access-roles and /permissions
    description = "Users, access roles (RBAC) with fine-grained permissions and per-user grants/denies."
    permissions = {
        "users:read": "List and view users",
        "users:create": "Create users",
        "users:update": "Edit users (profile, password, active flag)",
        "users:delete": "Delete users",
        "users:assign": "Change a user's roles, extra grants and denies",
        "access_roles:read": "View access roles and the permission catalog",
        "access_roles:create": "Create access roles",
        "access_roles:update": "Edit access roles",
        "access_roles:delete": "Delete access roles",
    }
    admin_resources = (
        AdminResource(
            key="users", label="Users", endpoint="/users",
            columns=(("Email", "email"), ("Name", "full_name"), ("Roles", "roles"), ("Active", "is_active")),
            read="users:read", create="users:create", update="users:update", delete="users:delete",
            readonly_fields=("_id", "created_at", "updated_at", "last_login", "token_version"),
            create_template={"email": "", "full_name": "", "password": "", "roles": ["viewer"], "grants": [], "denies": []},
            description="Add a 'password' key when editing to reset it.",
        ),
        AdminResource(
            key="access_roles", label="Access roles", endpoint="/access-roles",
            columns=(("Role", "_id"), ("Description", "description"), ("Permissions", "permissions")),
            read="access_roles:read", create="access_roles:create", update="access_roles:update",
            delete="access_roles:delete",
            readonly_fields=("_id", "builtin", "created_at", "updated_at"),
            create_template={"_id": "new-role", "description": "", "permissions": []},
        ),
    )

    def router(self):
        return router

    async def ensure_indexes(self, ctx: AppContext) -> None:
        await db.users().create_index("email", unique=True)

    async def on_startup(self, ctx: AppContext) -> None:
        await ensure_defaults(ctx)

    async def stats(self, ctx: AppContext):
        return {
            "users": await db.users().count_documents({}),
            "active_users": await db.users().count_documents({"is_active": True}),
            "access_roles": await db.access_roles().count_documents({}),
        }


module = UsersModule()
