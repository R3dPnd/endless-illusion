# Recon — digitalocean-bounty-2026-11 (Intigriti, DigitalOcean)

Passive only. Scope authority: `scope-verdict.md` (policy snapshot 2026-11-05). Recon date: 2026-11-23.
Sources: crt.sh, search engines, third-party pages. **No traffic was sent to any target.**
Performed by saudade-of-sunday; written to disk by the orchestrator (the agent had no write tool).

**Source gaps:** crt.sh returned 502/timeout for `%.digitaloceanpartners.com`, `%.digitaloceanstatus.com`,
`%.do.co`, `%.do-ai.run` (one attempt each). The `%.digitalocean.com` result was ~1.96M chars; only the
first 100k were read, so that list is partial. `api`, `cloud`, `amd`, `marketplace.digitalocean.com` were not
seen in the read portion; absence proves nothing.

## 1. In-scope asset inventory

### Named assets observed passively

| Host | Tier | Evidence (crt.sh ID) | Notes |
|---|---|---|---|
| `*.digitalocean.com` / `digitalocean.com` | 3 | 27915519578 (also Google WE1/WR1, LE, Sectigo, GlobalSign) | Multi-CA wildcard |
| `digitaloceanmirrors.com` | 2 | 29595698505; 28754126355; 9106665695 (Cloudflare ECC CA-3) | 80 records; only the apex is in scope |
| `digitaloceantest.com` | 2 | 29973248987; 29885810911; 25398471690; 11759619088 (Cloudflare) | Only the apex is in scope |
| `hacktoberfest.com` | 2 | 29770658382; 29874297072 | 151 records; only the apex is in scope |

### Named assets with no passive data
- Not seen in the read CT portion: `api`, `cloud`, `amd`, `marketplace`, `www`, `hackathon-tracker` `.digitalocean.com`, and `inference.do-ai.run`.
- crt.sh errors: `digitaloceanpartners.com`, `digitaloceanstatus.com`, `do.co`.

### Wildcard-derived hosts under `*.digitalocean.com` (not named assets; scope ambiguity 5, so ask before touching)

| Host | crt.sh ID | Issuer | Flag |
|---|---|---|---|
| `gradient-sdk.digitalocean.com` | 27881027193 | Google WE1/WR1 | AI platform SDK/docs |
| `docs.mcp.digitalocean.com` | 27837777702 | Google | MCP family |
| `genai-custom-models.mcp` | 27735301050 | Google | MCP |
| `genai-inferencerouter.mcp` | 27451087935 | Google | MCP |
| `genai-evaluation.mcp` | 27401869690 | Google | MCP |
| `genai-batchinference.mcp` | 27358736368 | Google | MCP |
| `codex.mcp` | 27451088328 | Google | MCP |
| `nfs.mcp` | 27402622346 | Google | MCP |
| `dedicated-inference.mcp` | 27397376947 | Google | MCP |
| `inference-modelcatalog.mcp` | 27322476084 | Google | MCP |
| `volumes.mcp` | 27174717894 | Google | MCP |
| `functions.mcp` | 27001591169 | Google | MCP |
| `droplets.mcp` | 26912011080 | Google | MCP |
| `networking.mcp` | 26775390651 | Google | MCP |
| `marketplace.mcp` | 26774234509 | Google | MCP (≠ `marketplace.digitalocean.com`) |
| `accounts.mcp` | 26770264347 | Google | MCP |
| `apps.mcp` | 26820118498 | Google | MCP |
| `insights.mcp` | 26818728444 | Google | MCP |
| `spaces.mcp` | 26906202774 | Google | MCP |
| `doks.mcp` | 26766628860 | Google | MCP |
| `databases.mcp` | 26766081815 | Google | MCP |
| `docr.mcp` | 26410914843 | Google | MCP; registry-related, possibly customer-adjacent |
| `*.sonar.digitalocean.com` | 26077914564 | GlobalSign Atlas R3 | Code-quality tooling? |
| `*.sonarsunset.digitalocean.com` | 25525441727 | LE YE2 | "sunset" suggests decommissioned |
| `test-docr.digitalocean.com` (+ wildcard) | 27578875259 | LE YE1 | Test registry; possibly stale |
| `vpn-staging.digitalocean.com` (+ www) | 26075992220 | DigiCert G2 | Staging VPN |
| `sbc.digitalocean.com` | 26127676910 | DigiCert G2 | Session border controller? |
| `repos-droplet.digitalocean.com` | 27157396991 | LE YE2 | Agent package repo |
| `repos.insights.digitalocean.com` | 26489268083 | LE E7 | Agent package repo |
| `cloudflareinproduction.storage.digitalocean.com` | 26487812426 | LE E8 | Storage/Spaces-related |
| `try.digitalocean.com` | 26471567520 | LE E8 | Marketing landing page |
| `store.digitalocean.com` | 26383308944 | LE R13 | Merch store, likely third-party |
| `outreach.digitalocean.com` | 27619686212 | LE YR1 | Sales tooling, likely third-party |
| `pages.news.digitalocean.com` | 27718439569 | Google | Marketing platform |
| `pages.support.digitalocean.com` | 27695685418 | Google | Marketing platform |
| `email.comms.digitalocean.com` | 27679794339 | LE YE2 | Adjacent to the excluded `email.` subdomain |

## 2. Tech fingerprints (public data only)

| Asset | Fingerprint | Basis |
|---|---|---|
| `digitaloceanmirrors.com`, `digitaloceantest.com` | Behind Cloudflare | `sni.cloudflaressl.com` certs |
| `hacktoberfest.com` | Static Next.js front end (version unknown) + closed-source hackathon-tracker API | Hacktoberfest GitHub repo description (2022; not confirmed for the current season) |
| `hackathon-tracker.digitalocean.com` | Closed-source backend API for hacktoberfest.com | Same |
| `www` / `cloud.digitalocean.com` | React + TypeScript + GraphQL/Apollo micro-frontends; legacy Ember app | Job posts (weakest source, not mapped to hosts) |
| `*.mcp.digitalocean.com` | Per-product MCP servers; stack unknown | CT names only |

No software versions were found in any public source.

## 3. Notable observations (unverified; do not verify by contacting hosts)

1. **MCP server sprawl.** 20+ `*.mcp.digitalocean.com` hosts got certs from late 2025 into 2026. They map to product APIs (accounts, databases, droplets, spaces) and likely expose account-scoped functionality. They are wildcard-derived, so ask before touching any.
2. **Environment-sounding names:** `vpn-staging`, `test-docr`, `sonarsunset`, `sbc`.
3. **Stale-CNAME candidates:** `sonarsunset`, `test-docr`, `vpn-staging`. No passive DNS confirmation. Note that a subdomain takeover without an actual takeover is excluded as low value.
4. **`scim-sandbox.digitaloceantest.com`** (e.g. 22170925975). A subdomain of a non-wildcard domain, so presumed out.
5. **Package repos** (`repos-droplet`, `repos.insights`) are informational only, because supply-chain targeting is prohibited.
6. **Cloudflare fronts** the mirrors and test domains.

## 4. Excluded or ambiguous

**Excluded by the verdict:**
- `ir`, `investors`, `investor`, `waves`, `ideas`, `rewards`, `anchor`, `groove`, `events` (`.digitalocean.com`)
- `registry.digitalocean.com` and `*.registry.digitalocean.com` (cert 27381409213)
- `paperspace.com`, `*.snapshooter.com`: not searched
- AS14061 and IP-based attribution: not used

**Ambiguous (do not target without operator confirmation):**
- `email.comms`, `pages.news`, `pages.support`, `store`, `outreach`, `try`: likely third-party platforms
- All wildcard-derived hosts above; `docr.mcp` and `test-docr` may be customer-adjacent
- `scim-sandbox.digitaloceantest.com`, and subdomains of `hacktoberfest.com`, `digitaloceanmirrors.com`, `digitaloceantest.com`

## Follow-ups
- Retry crt.sh for the four domains that errored; read the rest of the `%.digitalocean.com` results.
- Any active confirmation needs an operator-confirmed scope snapshot and the authorized-active toolset. Not authorized.
