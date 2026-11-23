# Scope verdict: digitalocean-bounty-2026-11 (Intigriti, DigitalOcean)

Prepared by Sen of Saturday. Basis: `policy.md` (platform snapshot retrieved 2026-11-05T00:30:13Z; assets version 2026-11-03, out-of-scope text 2026-10-22, RoE 2026-07-30, in-scope text 2026-08-14). Only the newest version of each section was used.

## Authorization status (read first)

- This phase is PASSIVE ONLY. Nothing in this document authorizes sending traffic to any target.
- The `get_scope`, `find_prior_work` and `propose_scope` tools are not available to this agent, so no operator-confirmed scope snapshot was checked and none was recorded. Under the RoE a scope proposal or this table is not authorization. Active work needs an operator-confirmed scope snapshot (see Ambiguities 1).
- No prior engagement work for this program was found in the repo (only the files in this directory). The pnd-notes base has only `security/bounty-landscape-2026-10-15`, a program-selection survey that says it gives no authorization.
- The snapshot is about 18 days old. Re-check the live policy before any active step.

## 1. In-scope assets (conditional on a later authorization decision)

Tier ids come from the platform. Tier 3 pays the most (up to $10,000), tier 2 less (up to $3,000), tier 1 pays no bounty, and tier 5 is out of scope.

| Asset | Type | Tier | Verdict | Conditions / notes |
|---|---|---|---|---|
| `*.digitalocean.com` | wildcard | 3 | IN, except the out-of-scope subdomains in section 2 | Check every hostname against section 2 first. `digitalocean.com/community/*` is third-party tooling, and many reports there hit exclusion 15.1. |
| `169.254.169.254` | IP | 3 | IN, but only from a Droplet you own | Metadata service at http://169.254.169.254/ "from Droplets". It is link-local and cannot be reached from outside. Recon agents have nothing to do here. |
| `api.digitalocean.com` | web/API | 3 | IN | Use only your own account and tokens. |
| `cloud.digitalocean.com` | web | 3 | IN | Test only accounts and resources you own. If you find a path into other accounts, STOP and take no further action against them. Findings on your own resources (databases, Spaces, Apps, Functions, K8s, registries, AI agents) are filed here. |
| `amd.digitalocean.com` | web | 3 | IN | Same rules as cloud; the policy says the two share a backend. |
| `inference.do-ai.run` | API | 3 | IN | Serverless Inference API. |
| `marketplace.digitalocean.com` | web | 3 | IN, but not the vendor content | 1-click apps and add-ons are maintained by vendors and are out of scope. |
| `www.digitalocean.com` | web | 2 | IN | Includes `www.digitalocean.com/community`. |
| `digitaloceanmirrors.com` | web | 2 | IN | |
| `digitaloceanpartners.com` | web | 2 | IN | |
| `digitaloceanstatus.com` | web | 2 | IN | Not the same as `status.digitalocean.com`, which is out of scope. |
| `digitaloceantest.com` | web | 2 | IN | |
| `do.co` | web | 2 | IN | Company shortlink service. |
| `hackathon-tracker.digitalocean.com` | web/API | 2 | IN | API for hacktoberfest.com. |
| `hacktoberfest.com` | web | 2 | IN | |
| `paperspace.com` | web | 1 | IN, no bounty | No rewards for `paperspace.com` or its subdomains. Treat it as low value. |
| `*.snapshooter.com` | wildcard | 5 | AMBIGUOUS, treat as out | See Ambiguities 3. |
| Open source GitHub repos | code | 1 (5 for some) | See below | |

GitHub repos (reading public source is passive):

- Tier 1: `digitalocean/do-agent`, `digitalocean/droplet-agent`, `digitalocean/doctl`. The prose also says the do-agent and droplet-agent repos are not eligible for bounty rewards.
- Tier 5: `action-doctl`, `godo`, `pydo`, `terraform-provider-digitalocean`, `go-nbd`, `do-markdownit`.
- All other DigitalOcean open source projects are out of scope.

Product scope named in prose (all tested only through your own account): AI-Native Cloud (Inference, Model Catalog, Playground, Serverless and Dedicated Inference, Router, Evaluations, Batch, Agent Platform, GPU Droplets, 1-Click Models), Droplets, Kubernetes, App Platform, Functions, Managed Databases, Vector Databases, Knowledge Bases, Volumes, Spaces, NFS, Snapshots, Backups, SnapShooter, Custom Images, Container Registry, DNS, Reserved IPs, Load Balancers, Firewalls, IPv6, VPC, DDoS Protection, CSPM, Monitoring, Projects, Uptime, Accounts/2FA/SSH keys, Teams, Organizations, the public API, doctl, do-agent and droplet-agent.

Database routing:

- Report MongoDB, Weaviate, Advanced Edition PostgreSQL and Advanced Edition MySQL to DigitalOcean.
- Report Standard Edition PostgreSQL, Standard Edition MySQL, Valkey, Kafka and OpenSearch to Aiven (https://bugcrowd.com/engagements/aiven-mbb-og).

## 2. Out-of-scope assets

### 2a. "*.digitalocean.com Out of Scope Subdomains" (all 20, exactly as in the policy)

- `anchor.digitalocean.com`
- `brand.digitalocean.com`
- `cloudsupport.digitalocean.com`
- `deploy.digitalocean.com`
- `email.digitalocean.com`
- `events.digitalocean.com`
- `go.digitalocean.com`
- `groove.digitalocean.com`
- `helpdesk.digitalocean.com`
- `ideas.digitalocean.com`
- `investor.digitalocean.com`
- `investors.digitalocean.com`
- `ir.digitalocean.com`
- `mirrors.digitalocean.com`
- `pilot.digitalocean.com`
- `rewards.digitalocean.com`
- `segment.digitalocean.com`
- `status.digitalocean.com`
- `tracking.digitalocean.com`
- `waves.digitalocean.com`

Also stated in that section:

- "Public IPs belonging to AS14061 (DigitalOcean, LLC) are assigned to DigitalOcean customers and should be considered out of scope."
- `digitalocean.com/community/*` is described as third-party tools built by the DO community. Many reports there fall under exclusion 15 (Outdated Domains & Static Links, 15.1).

### 2b. "Out of Scope: Customer Resources" (9 entries)

Customer resources are out of scope, except resources in your own account, which you file under `cloud.digitalocean.com`.

- `*.db.ondigitalocean.com`
- `*.db1.ondigitalocean.com`
- `*.digitaloceanspaces.com`
- `*.doserverless.co`
- `*.k8s.ondigitalocean.com`
- `*.ondigitalocean.app`
- `registry.digitalocean.com/*`
- `*.agents-internal.do-ai.run`. Customer-deployed agents at `adk-agent-{id}.agents-internal.do-ai.run` are out of scope. Your own agents are in scope, except for agent model vulnerabilities.
- "Assets created by other DigitalOcean customers": "Any asset (Droplet, Space, or otherwise) created by other DigitalOcean customers are not to be tested under any circumstances."

### 2c. "Out of Scope" (5 entries)

- `*.doserverless-dev3.io`
- `*.ondbaasdev.com`
- `*.onstagingocean.app`
- Marketplace Apps and Add-Ons. They are vendor maintained; contact security@digitalocean.com to have DigitalOcean pass an issue to the vendor.
- Other DigitalOcean open source projects not listed.

### 2d. Implicit and derived exclusions

- Any IP in AS14061, and any host reached only through Shodan-style or IP-based attribution, is a customer asset until proven otherwise.
- `ssrf-sheriff.internal.digitalocean.com` and `ssrf-sheriff.s2r1.internal.digitalocean.com` (FAQ) are the only internal hosts that may be targeted, and only to prove an SSRF you found in an in-scope asset. They are not recon targets. Any other internal resource needs explicit permission from DigitalOcean.
- Cloudways is a separate program and is not covered here.

## 3. Rules and prohibited techniques relevant to recon

Automated scanning:

- Machine-readable RoE `testingRequirements`: `automatedTooling: 10`. The policy text never explains this number. Intigriti normally uses it as a cap on requests per second, so the likely reading is that automated tooling is allowed up to 10 requests per second.
- The policy does not prohibit automated scanning outright. Even so, the number and its meaning are not confirmed, so treat the reading as unverified.
- The out-of-scope text says: "Please do not submit findings from automated scans unless you have verified and have high confidence that the vulnerable targets are part of DigitalOcean's public infrastructure and have a demonstrated security impact." Repetitive submissions against customers "may result in expulsion".
- Do not use Shodan-style or IP-range sweeps to choose targets. Those hits are usually customer assets that must never be tested.

Required or encouraged conditions (`testingRequirements`):

- `intigritiMe: true`. Use accounts registered with an `@intigriti.me` email. Accounts that do not use it may be locked or banned.
- Request header: `X-BBP-Researcher: {Username}`, where Username is the Intigriti username. It is encouraged but not required. The target host must not receive it until the operator supplies a real username.
- User-Agent: none required (empty).
- Do not host personal or commercial applications on the `@intigriti.me` account's servers.

Account and resource limits:

- Test only your own accounts and resources. Targeting DigitalOcean users or their resources (Droplets, Spaces, databases and so on) is NOT allowed.
- Do not exfiltrate content from DigitalOcean without explicit advance permission, and never exfiltrate customer content.
- If you find cross-account access, stop and take no further action against those accounts or data.
- Self-registration at https://cloud.digitalocean.com/registrations/new gives $5 credit and requires a valid credit card. Spin down resources after testing. No reimbursement is offered.
- Avoid privacy violations, data destruction and service degradation.

Prohibited or excluded (do not test or report):

- DoS/DDoS and brute force (21.1).
- Social engineering, spam, physical access, man-in-the-middle, compromised accounts, targeting DO employee workstations (20).
- Publicly known processor side-channel attacks (17). Contact security@digitalocean.com first.
- Blind SSRF without proven impact. Use the ssrf-sheriff endpoints only to prove SSRF, and put the username in the header and a query parameter.
- Do not attempt SSRF against other internal resources without explicit permission.
- Reportable but not bounty-eligible: upstream and third-party vendor vulnerabilities (23), and zero-days and CVEs within 30 days of patch release (24).
- Not rewarded: leaked secrets, unless a DO platform flaw caused the leak (25).
- Low-value or excluded classes (do not spend effort on them):
  - Version and banner disclosure, missing headers and cookie flags, rate-limit absence, and subdomain takeover without an actual takeover.
  - Email spoofing, SPF, DMARC and DKIM issues.
  - Unproven known-vulnerable libraries.
  - Host header injection without business impact.
  - Clickjacking, self-XSS and low-impact CSRF.
- Do not discuss or disclose vulnerability information without prior written consent.
- Sanctions restriction: do not participate if you are resident in a sanctioned region or on a sanctions list.

Acceptable PoCs (for later reference): `whoami`, `hostname`, `uname`; reading `/etc/hostname`; writing `/tmp/bbp_<intigriti username>`; basic SQLi evidence, optionally the database username.

AI tooling: the FAQ endorses a "Human in the Loop" approach. Machine-generated reports without human validation are discouraged.

## 4. Ambiguities for the operator to resolve

1. Authorization basis: no operator-confirmed scope snapshot exists and the scope tools were not reachable from this agent. Before any active step, the operator must confirm the snapshot (or the live policy) and record it.
2. `automatedTooling: 10` has no unit or explanation in the policy text. Likely 10 requests per second, but unconfirmed. Confirm with the Intigriti UI or DigitalOcean support before any automated tooling.
3. `*.snapshooter.com` is listed as a wildcard asset with tier 5, which is the out-of-scope tier, and the platform also treats it as an in-scope product (SnapShooter is in the prose list). Treat as out of scope until DigitalOcean clarifies.
4. `hackathon-tracker.digitalocean.com` and `hacktoberfest.com` are in scope at tier 2, and `do.co` is a shortlink service. `do.co` is not under the `digitalocean.com` wildcard, so only the host as listed is in scope. Confirm that subdomains of the non-wildcard domains (for example `www.hacktoberfest.com` or hosts under `do.co`) count. Default: no.
5. The wildcard `*.digitalocean.com` has an exclusion list that may be incomplete. Any hostname not on the list is nominally in scope, but internal or customer-adjacent hosts (for example `*.internal.digitalocean.com`) are not intended targets. Ask before touching any wildcard-derived host that is not a named asset.
6. Marketplace: `marketplace.digitalocean.com` is in scope but vendor apps are not. A recon agent cannot tell vendor-hosted endpoints from DigitalOcean's own. Ask before touching any marketplace subresource.
7. Conflicting text on `do-agent` and `droplet-agent`: the platform lists them as tier 1 assets and the prose says they are not eligible for bounty rewards. Public source reading is passive, so this only affects whether reports are worthwhile.
8. Header `X-BBP-Researcher` needs the operator's Intigriti username. It was not provided. Do not invent one.
9. Intigriti account `@intigriti.me`: the operator needs one, and a credit card, before testing can start. Confirm availability.
10. Retrieval age: the snapshot dates from 2026-11-05. Re-fetch before any active phase.

## Hand-off guidance for recon and CVE agents

- Passive only: certificate transparency, public DNS datasets, GitHub source, docs.digitalocean.com, advisories, and CVE databases. Do not send traffic to any hostname in section 1 or 2.
- Drop every hostname in section 2 from candidate lists. If an asset's status is unclear, treat it as out of scope and ask.
- Do not attribute assets by IP or ASN. Never use AS14061 ranges as target lists.
