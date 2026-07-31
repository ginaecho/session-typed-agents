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
import threading
import time
from dataclasses import dataclass


@dataclass
class _Token:
    token: str
    expires_on: int


# Process-wide token cache + lock, shared across ALL AzCliCredential instances.
# Concurrent agent creation fires many get_token() calls at once; each `az`
# call is ~8-13s when the globally-active account differs from the pinned
# subscription (az context-switches every call), so a storm of them piles up on
# az's own MSAL cache lock and blows the timeout. Double-checked locking here
# collapses the storm to ONE az call per (sub, tenant, resource) — the first
# caller fetches, the rest wait briefly then hit the cache. Key includes the
# sub/tenant so distinct pins never share a token.
_TOKEN_CACHE: dict[tuple, _Token] = {}
_TOKEN_LOCK = threading.Lock()
_AZ_TIMEOUT_S = 120


class AzCliCredential:
    """Minimal credential that shells out to `az account get-access-token`."""

    def __init__(self, tenant_id: str | None = None,
                 subscription_id: str | None = None):
        # Pin token acquisition so it survives az default-account changes
        # (observed repeatedly: another project's `az login` flips the global
        # default mid-campaign and get-access-token starts minting
        # wrong-tenant tokens, failing every new-agent creation).
        #
        # PREFER --subscription over --tenant. On guest/multi-tenant accounts
        # `--tenant <resource-tenant>` returns AADSTS invalid_grant
        # (interactive re-auth required), whereas `--subscription <id>` mints a
        # correct resource-tenant token from the still-cached credential even
        # when a different account is globally active (verified 2026-07-30).
        # `az` rejects passing BOTH, so subscription wins when both are set.
        # Set STJP_AZURE_SUBSCRIPTION_ID (preferred) or STJP_AZURE_TENANT_ID in
        # stjp_core/.env to the Foundry resource's subscription / tenant.
        self.subscription_id = subscription_id or os.environ.get("STJP_AZURE_SUBSCRIPTION_ID")
        self.tenant_id = tenant_id or os.environ.get("STJP_AZURE_TENANT_ID")

    def _fresh(self, tok: _Token | None) -> bool:
        return bool(tok) and tok.expires_on - 60 > int(time.time())

    def get_token(self, *scopes: str) -> _Token:
        if not scopes:
            raise ValueError("At least one scope is required")
        # Convert "https://x/.default" → resource "https://x"
        scope = scopes[0]
        resource = scope[: -len("/.default")] if scope.endswith("/.default") else scope
        key = (self.subscription_id, self.tenant_id, resource)

        # Fast path: token already cached and fresh (no lock, no az call).
        if self._fresh(_TOKEN_CACHE.get(key)):
            return _TOKEN_CACHE[key]

        # Slow path: serialize so a burst of concurrent callers makes ONE az
        # call, not N. Re-check under the lock (another thread may have just
        # populated it while we waited).
        with _TOKEN_LOCK:
            if self._fresh(_TOKEN_CACHE.get(key)):
                return _TOKEN_CACHE[key]

            cmd = ["az", "account", "get-access-token", "--resource", resource, "-o", "json"]
            # subscription pin takes precedence (survives global-account flips);
            # az forbids passing both --subscription and --tenant.
            if self.subscription_id:
                cmd += ["--subscription", self.subscription_id]
            elif self.tenant_id:
                cmd += ["--tenant", self.tenant_id]

            # shell=True makes Windows resolve az -> az.cmd. Timeout guards
            # against az hanging on its MSAL cache lock (froze runs for hours,
            # 2026-07-25/27); on timeout we raise so the caller can retry.
            try:
                result = subprocess.run(
                    " ".join(cmd), shell=True, capture_output=True, text=True,
                    timeout=_AZ_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"az get-access-token timed out after {_AZ_TIMEOUT_S}s") from exc
            if result.returncode != 0:
                raise RuntimeError(f"az get-access-token failed: {result.stderr}")
            data = json.loads(result.stdout)
            expires_on = int(data.get("expires_on", time.time() + 3500))
            token = _Token(token=data["accessToken"], expires_on=expires_on)
            _TOKEN_CACHE[key] = token
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
