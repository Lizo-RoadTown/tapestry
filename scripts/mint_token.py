"""Mint a self-host JWT for the loom memory MCP.

Dev-mode shortcut for Phase 2 MVP. You are the only user; you have the
private key; you self-issue tokens. Proper OAuth flow lands in V2.x.

Usage (PowerShell):
    python scripts/mint_loom_token.py

    # Or with a custom expiry in hours (default 24):
    python scripts/mint_loom_token.py --hours 720   # 30 days

The script reads the private key from ~/.ssh/loom_jwt, signs an RS256
JWT with these claims:
    sub:        "liz"                                  (subject = user id)
    tenant_id:  "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8" (stable self-host UUID;
                                                       matches mcp_server.py:62)
    iat:        <now>                                  (issued at)
    exp:        <now + hours>                          (expiry)
    iss:        "loom-self-host"                       (issuer)

Prints the token to stdout and a ready-to-paste `.claude/mcp.json`
snippet to stderr. Pipe the token into a clipboard if needed:
    python scripts/mint_loom_token.py | Set-Clipboard

Uses PyJWT (already installed in Liz's env). Doesn't write the token
to disk — short-lived secret, printed only.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import jwt as pyjwt  # PyJWT


# Constants matching services/agent-context/mcp_server.py:62
SELF_HOST_TENANT_ID = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"
ISSUER = "loom-self-host"
DEFAULT_SUBJECT = "liz"

# Env-override precedence for Tapestry migration (PR-prep-2b 2026-06-19):
#   1. TAPESTRY_MEMORY_MCP_URL: Tapestry-aware full URL; highest precedence
#   2. LOOM_MEMORY_MCP_URL: pre-Tapestry full URL
#   3. TAPESTRY_MEMORY_URL: Tapestry-aware bare base; /mcp/memory/ composed
#   4. LOOM_MEMORY_URL: pre-Tapestry bare base; /mcp/memory/ composed
#   5. Hardcoded default — the-loom's Render deployment
MCP_URL = os.environ.get(
    "TAPESTRY_MEMORY_MCP_URL",
    os.environ.get(
        "LOOM_MEMORY_MCP_URL",
        f"{os.environ.get('TAPESTRY_MEMORY_URL', os.environ.get('LOOM_MEMORY_URL', 'https://loom-agent-context.onrender.com')).rstrip('/')}/mcp/memory/",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Token validity in hours (default: 24)",
    )
    parser.add_argument(
        "--sub",
        default=DEFAULT_SUBJECT,
        help=f"JWT 'sub' claim (default: {DEFAULT_SUBJECT})",
    )
    parser.add_argument(
        "--key",
        default=str(Path.home() / ".ssh" / "loom_jwt"),
        help="Path to PEM-formatted RSA private key (default: ~/.ssh/loom_jwt)",
    )
    args = parser.parse_args()

    key_path = Path(args.key)
    if not key_path.exists():
        print(f"error: private key not found at {key_path}", file=sys.stderr)
        print(
            "       Regenerate with:\n"
            "         ssh-keygen -t rsa -b 4096 -m PEM -f \"$env:USERPROFILE\\.ssh\\loom_jwt\" -N '\"\"'\n",
            file=sys.stderr,
        )
        return 1

    private_key_pem = key_path.read_text(encoding="utf-8")

    now = int(time.time())
    claims = {
        "sub": args.sub,
        "tenant_id": SELF_HOST_TENANT_ID,
        "iat": now,
        "exp": now + (args.hours * 3600),
        "iss": ISSUER,
    }

    token = pyjwt.encode(claims, private_key_pem, algorithm="RS256")

    # Token to stdout — pipeable into clipboard or env var
    print(token)

    # Diagnostic info to stderr
    print(
        f"\n--- minted RS256 JWT ---\n"
        f"  subject:    {claims['sub']}\n"
        f"  tenant_id:  {claims['tenant_id']}\n"
        f"  issuer:     {claims['iss']}\n"
        f"  valid for:  {args.hours}h (expires {time.ctime(claims['exp'])})\n"
        f"\n--- .claude/mcp.json snippet ---\n"
        '{\n'
        '  "mcpServers": {\n'
        '    "loom-memory": {\n'
        f'      "url": "{MCP_URL}",\n'
        '      "transport": {\n'
        '        "type": "http",\n'
        '        "headers": {\n'
        f'          "Authorization": "Bearer <PASTE-TOKEN-HERE>"\n'
        '        }\n'
        '      }\n'
        '    }\n'
        '  }\n'
        '}\n',
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
