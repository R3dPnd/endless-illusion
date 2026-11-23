# Engagement: digitalocean-bounty-2026-11 — passive full-scope recon

- **Date:** 2026-11-23
- **Agent(s):** dann-of-thursday (orchestrator), sen-of-saturday (scope), saudade-of-sunday (recon), dahlia-of-wednesday (CVE research)
- **Target(s):**
  - Tier 3: `*.digitalocean.com` (minus exclusions), `api.`, `cloud.`, `amd.`, `marketplace.digitalocean.com`, `inference.do-ai.run`
  - Tier 2: `www.digitalocean.com`, `digitaloceanmirrors.com`, `digitaloceanpartners.com`, `digitaloceanstatus.com`, `digitaloceantest.com`, `do.co`, `hackathon-tracker.digitalocean.com`, `hacktoberfest.com`
- **Authorization:** Intigriti DigitalOcean bug bounty program. This phase is **passive public research only**, which needs no further authorization. No operator-confirmed scope snapshot exists, so **no active testing is authorized**.
- **Scope & exclusions:** see `scope-verdict.md` (policy snapshot 2026-11-05):
  - 20 excluded `*.digitalocean.com` subdomains
  - All customer-resource domains (`*.ondigitalocean.app`, `*.digitaloceanspaces.com`, etc.)
  - AS14061 / IP-picked targets (customer space)
  - Marketplace vendor apps
  - `*.snapshooter.com` (ambiguous, treated as out)

## Summary

We mapped DigitalOcean's in-scope attack surface from public sources only: certificate transparency, search results, public GitHub and docs, and CVE databases. No traffic was sent to any DigitalOcean host. **There are no confirmed findings, which is expected for a passive pass.** The strongest lead is a family of 20+ new `*.mcp.digitalocean.com` MCP servers that likely expose account-scoped product functions. They are only in scope through the wildcard, so check with the program before touching them. No software versions were found publicly, so every CVE lead is unconfirmed.

## Findings

No confirmed vulnerabilities. Leads, ranked:

### L-01 MCP server family under `*.mcp.digitalocean.com`
- **Status:** Suspected attack surface. Not a vulnerability.
- **Severity:** Info for now. Potentially High if tool authorization or token scoping is flawed.
- **Affected:** 20+ hosts, e.g. `accounts.mcp`, `databases.mcp`, `droplets.mcp`, `spaces.mcp`, `docr.mcp` (see `recon.md` §1).
- **Description:** Per-product MCP servers that got certs from late 2025 into 2026. Their likely risks are design-level (authorization against the caller's token, confused deputy, token scoping) rather than SDK CVEs. DNS rebinding and Origin CVEs mostly affect localhost servers.
- **Next step:** Passive first: read docs.digitalocean.com MCP pages and the `go.mod` of the public `digitalocean-labs/mcp-digitalocean` repo. Any connection to these hosts needs operator confirmation of scope plus authorization.

### L-02 Control panel / API authorization logic
- **Status:** Suspected. Hypothesis only.
- **Affected:** `cloud.digitalocean.com`, `api.digitalocean.com` (React + Apollo micro-frontends, per job posts)
- **Description:** Library CVEs are unlikely to apply to a client-side SPA. Authorization (IDOR/BOLA) is the realistic payable class. Teams/RBAC/OAuth-app issues were already disclosed publicly (Imperva, 2023), so avoid them as duplicates.
- **Next step:** Authorized testing with the operator's own `@intigriti.me` account (diablo-of-monday / metsa-of-tuesday).

### L-03 Staging and retired hostnames
- **Status:** Suspected.
- **Affected:** `vpn-staging`, `test-docr`, `sonarsunset`, `sbc` (`.digitalocean.com`)
- **Description:** Names that sound internal or decommissioned; candidates for dangling DNS. A subdomain takeover only counts as a finding if the takeover is actually achieved.

### L-04 Next.js on hacktoberfest.com
- **Status:** Unconfirmed; probably not applicable.
- **Description:** Likely a static export, which has no middleware or RSC runtime. CVE-2025-29927 and CVE-2025-55182 would need a self-hosted Node server. Check the public repo's `next.config` and lockfile first.

## Out of scope / not tested

- **All active work.** No probing, scanning or crawling. It needs an operator-confirmed scope snapshot, a re-fetch of the 18-day-old policy, clarity on `automatedTooling: 10`, the operator's Intigriti username and an `@intigriti.me` account.
- **Ambiguous hosts held back:**
  - Wildcard-derived hosts (ambiguity 5)
  - Likely third-party platforms: `store`, `outreach`, `try`, `pages.*`, `email.comms`
  - Subdomains of non-wildcard tier 2 domains (e.g. `scim-sandbox.digitaloceantest.com`)
  - `*.snapshooter.com`
- **Package repos** (`repos-droplet`, `repos.insights`): informational only, because supply-chain targeting is prohibited.
- **Coverage gaps:** crt.sh errors for `digitaloceanpartners.com`, `digitaloceanstatus.com`, `do.co` and `do-ai.run`; only the first ~5% of the `%.digitalocean.com` CT result was read; one fetch of DigitalOcean's 2017 Cloudbleed blog post was denied by the permission system.
- **Tooling gaps:** Saudade, Sen and Dahlia had no hub-recording or write tools, so nothing went into the archive DB (record_asset / record_observation / save_cve_note / propose_scope). The orchestrator wrote the files.

## References

- `scope-verdict.md`, `recon.md`, `cve-research.md` (this directory)
- CVE-2025-29927, CVE-2025-55182 (KEV), CVE-2026-44574/44575/45109, CVE-2025-64173, CVE-2025-64530, CVE-2026-34742, CVE-2026-33252
- Imperva, "Navigating the Sea, Exploiting DigitalOcean APIs" (2023) — https://imperva.com/blog/?p=18527
- DigitalOcean MCP docs — https://docs.digitalocean.com/reference/mcp/llms.txt
