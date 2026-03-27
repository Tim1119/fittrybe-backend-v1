"""
JWT WebSocket authentication middleware.
Authenticates via ?token=<JWT access token> query param.
Closes with code 4001 if token is missing or invalid.
"""

from urllib.parse import parse_qs


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.accounts.models import User

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        if not token_list:
            await send({"type": "websocket.close", "code": 4001})
            return

        try:
            access_token = AccessToken(token_list[0])
            user = await User.objects.aget(id=access_token["user_id"], is_active=True)
            scope["user"] = user
        except Exception:
            await send({"type": "websocket.close", "code": 4001})
            return

        await self.app(scope, receive, send)


# Keep backward-compatible name used by asgi.py before Phase 2
def JwtAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
