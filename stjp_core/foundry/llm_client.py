"""
LLM Client.

PROJECT POLICY: by default, every LLM call routes through Azure AI Foundry's
Agent Service (FoundryLLMClient) so the interaction is visible in the portal
under Agents -> stjp-utility -> Threads. This produces a complete audit trail.

Set STJP_LLM_BACKEND=chat in .env (or the environment) to use the legacy
direct-chat-completions path for cost/latency-sensitive batch use cases.

Authentication:
    Run `az login` before using this module.

Environment:
    AZURE_AI_PROJECT_ENDPOINT  -- Foundry project endpoint (default backend)
    AZURE_OPENAI_ENDPOINT      -- Azure OpenAI endpoint  (legacy backend)
    AZURE_OPENAI_DEPLOYMENT    -- Model deployment name
    STJP_LLM_BACKEND           -- 'foundry' (default) or 'chat'
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI
from stjp_core.foundry.az_credential import AzCliCredential, make_token_provider

# Canonical .env lives at stjp_core/.env (this file is stjp_core/foundry/).
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get Azure OpenAI config from .env
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
STJP_LLM_BACKEND = os.environ.get("STJP_LLM_BACKEND", "foundry").lower()


class _RawChatLLMClient:
    """
    Client for interacting with Azure OpenAI using Azure AD authentication.
    Requires `az login` before use.
    """
    
    def __init__(self, deployment: str | None = None):
        if not AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT not set in .env file!\n"
                "Add: AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/"
            )

        self.deployment = deployment or AZURE_OPENAI_DEPLOYMENT

        # Use az_credential.AzCliCredential (works around the Windows
        # azure-identity bug where AzureCliCredential can't find az.cmd).
        token_provider = make_token_provider("https://cognitiveservices.azure.com/.default")

        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_ad_token_provider=token_provider,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        # gpt-5 / o-series deployments reject `max_tokens` ("Unsupported
        # parameter ... use 'max_completion_tokens' instead"), while older
        # deployments reject `max_completion_tokens`. Rather than maintain a
        # model-name table that goes stale with every release, we learn the
        # right key from the service on the first 400 and remember it.
        self._token_param = "max_tokens"

    def _create(self, messages: list, max_tokens: int):
        """One chat completion, retrying once with the other token-limit
        parameter name if the deployment rejects the one we used."""
        try:
            return self.client.chat.completions.create(
                model=self.deployment, messages=messages,
                **{self._token_param: max_tokens})
        except Exception as e:
            other = ("max_completion_tokens"
                     if self._token_param == "max_tokens" else "max_tokens")
            if other not in str(e):
                raise
            self._token_param = other
            return self.client.chat.completions.create(
                model=self.deployment, messages=messages,
                **{self._token_param: max_tokens})


    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """
        Generate a response from Azure OpenAI.
        
        Args:
            system_prompt: The system instructions
            user_prompt: The user's request
            max_tokens: Maximum tokens in response
            
        Returns:
            The generated text response
        """
        try:
            response = self._create(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": user_prompt}], max_tokens)
            return response.choices[0].message.content
        except Exception as e:
            # Print full error details
            print(f"\n[DEBUG] Full error: {e}")
            raise
    
    def generate_with_history(self, system_prompt: str, messages: list, max_tokens: int = 4096) -> str:
        """
        Generate a response with conversation history.

        Args:
            system_prompt: The system instructions
            messages: List of {"role": "user"|"assistant", "content": str}
            max_tokens: Maximum tokens in response

        Returns:
            The generated text response
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        response = self._create(full_messages, max_tokens)
        return response.choices[0].message.content


# Public LLMClient -- routes through Foundry Agent Service by default.
# Override with STJP_LLM_BACKEND=chat for the legacy direct path.

if STJP_LLM_BACKEND == "chat":
    LLMClient = _RawChatLLMClient
else:
    # Lazy import so a missing AZURE_AI_PROJECT_ENDPOINT only errors on use,
    # not on every import of this module.
    from stjp_core.foundry.foundry_client import FoundryLLMClient as LLMClient  # noqa: F401
