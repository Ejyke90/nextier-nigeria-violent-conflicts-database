Step 1 — Codebase Discovery

Review the entire codebase and identify every MCP service file.

List:
1. Every file that defines an endpoint, route, or handler
2. Every middleware file
3. Every auth or security utility file
4. Every config or environment file that references tokens, secrets, keys, or auth

Do not analyse yet. Just list what you found with file paths.
Wait for my confirmation before proceeding to Step 2.

Step 2 — Endpoint Inventory

For every file identified in Step 1, extract a complete flat list of every
endpoint or handler defined.

For each endpoint output exactly:
  - File path
  - HTTP method (GET / POST / etc) or transport type (SSE / WebSocket / stdio)
  - Route or handler name
  - Any middleware applied to it (list each one)

Do not assess security yet. Just map every endpoint.
Wait for my confirmation before proceeding to Step 3.

Step 3 — Security Assessment

For every endpoint in the inventory from Step 2, assess whether it is protected.

An endpoint is PROTECTED if it has at least one of:
  - Authentication middleware (JWT, OAuth, API key, session)
  - Authorization check (role, scope, permission guard)
  - MCP-level auth (e.g. Authorization header enforcement in SSE handshake)

An endpoint is UNPROTECTED if it has none of the above.

Output two tables:

PROTECTED ENDPOINTS
| File | Method | Route/Handler | Auth Mechanism |

UNPROTECTED ENDPOINTS
| File | Method | Route/Handler | Risk Level (High/Critical) |

Risk levels:
  - Critical = exposes data mutation, tool invocation, or sensitive reads
  - High = exposes any unauthenticated read or metadata

Wait for my confirmation before proceeding to Step 4.

Step 4 — Principal Security Engineer Recommendation

You are a Principal Security AI Engineer conducting an enterprise production
security review of an MCP service.

Based on the unprotected endpoints identified in Step 3, produce:

1. THREAT SUMMARY
   Plain language description of what an attacker could do with each
   unprotected endpoint today.

2. RECOMMENDED AUTH ARCHITECTURE
   Recommend a layered auth implementation appropriate for an MCP service
   at enterprise scale. Cover:
     - Transport-level auth (SSE handshake, WebSocket upgrade)
     - Request-level auth (per-call token validation)
     - Tool-level auth (per-tool permission scopes)
     - Service-to-service auth (internal MCP calls)

3. IMPLEMENTATION PLAN
   For each unprotected endpoint, provide:
     - The exact middleware or decorator to add
     - The recommended library (e.g. python-jose, authlib, fastapi-security,
       express-jwt, passport.js — match to the project's language and framework)
     - A code snippet showing the pattern (not a full rewrite — just the auth layer)
     - The design pattern used (e.g. middleware chain, dependency injection,
       decorator, guard)

4. SECURITY CONSTANTS
   List any hardcoded secrets, missing environment variable checks, or
   insecure defaults found during the review.

5. PRIORITY ORDER
   Rank all fixes from P0 (fix before next deploy) to P2 (fix this sprint).

Format the output so it can be shared directly as an engineering RFC.
Wait for my confirmation before writing any code.
