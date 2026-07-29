"""
AzCliCredential — a thin wrapper around `az account get-access-token` via shell=True.

Works around the Windows azure-identity AzureCliCredential issue where the bundled
azure-identity can't find `az` because it uses subprocess without shell=True (on
Windows, `az` is a .cmd file, not a directly executable binary).

Why this works: `az` is fully logged in via `az login`. We just call it via shell.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from dataclasses import dataclass


@dataclass
class _Token:
    token: str
    expires_on: int


class AzCliCredential:
    """Minimal credential that shells out to `az account get-access-token`."""

    def __init__(self, tenant_id: str | None = None):
        # Pin the tenant so token acquisition survives az default-subscription
        # changes (observed 2026-07-02: another process flipped the default
        # mid-run and get-access-token started minting wrong-tenant tokens).
        # Set STJP_AZURE_TENANT_ID in stjp_core/.env to the resource tenant.
        self.tenant_id = tenant_id or os.environ.get("STJP_AZURE_TENANT_ID")
        self._cache: dict[str, _Token] = {}

    def get_token(self, *scopes: str) -> _Token:
        if not scopes:
            raise ValueError("At least one scope is required")
        # Convert "https://x/.default" → resource "https://x"
        scope = scopes[0]
        resource = scope[: -len("/.default")] if scope.endswith("/.default") else scope

        cached = self._cache.get(resource)
        if cached and cached.expires_on - 60 > int(time.time()):
            return cached

        cmd = ["az", "account", "get-access-token", "--resource", resource, "-o", "json"]
        if self.tenant_id:
            cmd += ["--tenant", self.tenant_id]

        # shell=True is the magic that makes Windows resolve az -> az.cmd.
        # timeout=60: `az` can hang indefinitely on a token-cache lock, which
        # froze whole benchmark runs for hours with no socket-level timeout to
        # catch it (2026-07-25/27 stalls). On timeout we raise so the caller's
        # retry loop can re-attempt instead of hanging forever.
        try:
            result = subprocess.run(
                " ".join(cmd), shell=True, capture_output=True, text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"az get-access-token timed out after 60s") from exc
        if result.returncode != 0:
            raise RuntimeError(f"az get-access-token failed: {result.stderr}")
        data = json.loads(result.stdout)
        # expiresOn is local-time string; expires_on field (epoch) preferred
        expires_on = int(data.get("expires_on", time.time() + 3500))
        token = _Token(token=data["accessToken"], expires_on=expires_on)
        self._cache[resource] = token
        return token

    # azure-identity protocol expects this method too
    def get_token_info(self, *scopes: str, **kwargs):
        return self.get_token(*scopes)


def make_token_provider(scope: str = "https://cognitiveservices.azure.com/.default"):
    """Return a callable suitable for AzureOpenAI's azure_ad_token_provider param."""
    cred = AzCliCredential()
    def _provider() -> str:
        return cred.get_token(scope).token
    return _provider
