from __future__ import annotations

from resumehub.app.core.plugin import Module

from .router import router


class AuthModule(Module):
    name = "auth"
    description = "Login, token refresh, session revocation and password change."
    depends_on = ("users",)

    def router(self):
        return router


module = AuthModule()
