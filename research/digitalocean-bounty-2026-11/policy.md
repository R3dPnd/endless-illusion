# DigitalOcean (Intigriti) - raw policy

- Source: https://app.intigriti.com/api/core/public/programs/digitalocean/digitalocean
- Program status code: 3 | confidentiality level: 4
- Each section below is the newest version in the platform's history, with its timestamp.

## Description

DigitalOcean, LLC. is an American multinational technology company and cloud service provider. DigitalOcean simplifies cloud computing so developers and businesses can spend more time building software that changes the world.

## Assets (version 2026-11-03 18:39 UTC)

### `*.digitalocean.com`

- typeId: 7 | bountyTierId: 3

Please review the __*.digitalocean.com Out of Scope Subdomains__ section below to ensure testing of only in-scope domain assets.

### `169.254.169.254`

- typeId: 4 | bountyTierId: 3

Metadata service available at http://169.254.169.254/ from Droplets

### `api.digitalocean.com`

- typeId: 1 | bountyTierId: 3

### `cloud.digitalocean.com`

- typeId: 1 | bountyTierId: 3

Findings against resources owned by your account should be filed underneath this asset.

* While performing your research, please limit the scope of testing to only the accounts or resources that are owned by you.
* If you discover a vulnerability that could allow you to bypass existing controls and gain access to other accounts, **please do not take any further action** against those accounts or data that are not owned by you.

### `amd.digitalocean.com`

- typeId: 1 | bountyTierId: 3

This asset follows the same testing guidelines as `cloud.digitalocean.com`.

* While performing your research, please limit the scope of testing to only the accounts or resources that are owned by you.
* If you discover a vulnerability that could allow you to bypass existing controls and gain access to other accounts, **please do not take any further action** against those accounts or data that are not owned by you.

Note that we consider `cloud.digitalocean.com` and `amd.digitalocean.com` as having functionally the same backend codebase.

### `inference.do-ai.run`

- typeId: 1 | bountyTierId: 3

DigitalOcean Serverless Inference API

### `marketplace.digitalocean.com`

- typeId: 1 | bountyTierId: 3

Note that marketplace 1-click apps and add-ons are maintained by our partnered vendors and are out of scope. 
Please see the "Out of Scope" section below for more info.

### `www.digitalocean.com`

- typeId: 1 | bountyTierId: 2

Includes DigitalOcean Community, www.digitalocean.com/community

### `digitaloceanmirrors.com`

- typeId: 1 | bountyTierId: 2

### `digitaloceanpartners.com`

- typeId: 1 | bountyTierId: 2

### `digitaloceanstatus.com`

- typeId: 1 | bountyTierId: 2

### `digitaloceantest.com`

- typeId: 1 | bountyTierId: 2

### `do.co`

- typeId: 1 | bountyTierId: 2

Company shortlink service

### `hackathon-tracker.digitalocean.com`

- typeId: 1 | bountyTierId: 2

API for hacktoberfest.com

### `hacktoberfest.com`

- typeId: 1 | bountyTierId: 2

### `paperspace.com`

- typeId: 1 | bountyTierId: 1

We do not currently offer bounty rewards for findings related to the `paperspace.com` domain or associated sub-domains.

### `*.snapshooter.com`

- typeId: 7 | bountyTierId: 5

SnapShooter is a cloud backup and recovery solution.

### `Open Source GitHub Repos`

- typeId: None | bountyTierId: None

### `*.digitalocean.com Out of Scope Subdomains`

- typeId: None | bountyTierId: None

Public IPs belonging to AS14061(DigitalOcean, LLC) are assigned to DigitalOcean customers and should be considered out of scope.

Please note that `digitalocean.com/community/*` is a set of 3rd party tools built by our DO community, and many of the reported issues have fallen under our **Application-Specific Exclusions** for 
> 15. Outdated Domains & Static Links:
		15.1 Links on static content referencing outdated third-party domains.


**The following subdomains are out of scope:**

### `Out of Scope: Customer Resources`

- typeId: None | bountyTierId: None

These are customer-managed resources that are all out-of-scope.

### `Out of Scope`

- typeId: None | bountyTierId: None

These are general DigitalOcean out-of-scope assets.


## In scope (version 2026-08-14 15:20 UTC)

```json
{
  "content": "**Introduction**\nDigitalOcean is a cloud service provider offering infrastructure-as-a-service and platform-as-a-service solutions. DigitalOcean simplifies cloud computing so developers and businesses can spend more time building software that changes the world. At DigitalOcean, our customers’ trust is critical to us. We know that our customers need a secure foundation to build on, which is why we take security seriously. We look forward to working with the security community across the globe to find vulnerabilities in order to keep our customers and businesses safe. Please read the following content on how to best engage this program, stay within scope boundaries, and more.\n\nLooking for other DigitalOcean assets? Take a look at our other bug bounty programs:\n- [Cloudways by DigitalOcean](https://app.intigriti.com/programs/digitalocean/cloudways/detail)\n\n\n**High Impact Findings**\nWe are particularly interested in findings that enable widespread compromise of other customers or penetrate DigitalOcean’s core backend systems. These behaviors are not limited to specific vulnerability categories, but some examples include:\n* Broken authorization leading to access of other DigitalOcean customer records\n* Breaking out of process controls (e.g. access the hypervisor from your guest)\n* Remote code execution on core DigitalOcean infrastructure\n* Cross-VM attacks to break the multi-tenancy architecture\n\n**Acceptable PoCs**\n* Command execution: `whoami`, `hostname`, `uname`\n* File reads: `/etc/hostname`\n* File writes: `/tmp/bbp_<intigriti username>`\n* SQL injection: basic evidence (`' OR 1='1` causes all rows to return and `' AND 0='1` causes zero rows to return) is fine, but feel free to extract the username of the database user as well\n\n### DigitalOcean Products\n\n**DigitalOcean AI-Native Cloud**\n* [Inference](https://docs.digitalocean.com/products/inference/) - Single control plane for managing inference workflows that includes a Model Catalog\n    * [Model Catalog](https://docs.digitalocean.com/products/inference/how-to/browse-model-catalog/) - Discover, filter, and compare all available models as well as manage and deploy your imported models\n    * [Model Playground](https://docs.digitalocean.com/products/inference/how-to/use-model-playground/) - Try models side by side, tune parameters, and compare responses instantly\n    * [Serverless Inference](https://docs.digitalocean.com/products/inference/how-to/use-serverless-inference/) - Scale from zero automatically with per-token pricing and simple endpoints\n    * [Dedicated Inference](https://docs.digitalocean.com/products/inference/how-to/use-dedicated-inference/) - Provision dedicated GPUs for predictable latency and sustained throughput\n    * [Inference Router](https://docs.digitalocean.com/products/inference/how-to/use-inference-router/) - Route traffic across models with policies, fallbacks, and observability\n    * [Evaluations](https://docs.digitalocean.com/products/inference/how-to/evaluate-models/) - Analyze and evaluate models for your production use-cases with your datasets\n    * [Batch Inference](https://docs.digitalocean.com/products/inference/how-to/use-batch-inference/) - Run large offline jobs efficiently with batch APIs and workflows\n    * [Agent Platform](https://docs.digitalocean.com/products/inference/how-to/use-agent-platform/) - Create agents with tools, retrieval, and guardrails on the DigitalOcean AI platform\n* [GPU Droplets](https://docs.digitalocean.com/products/gpu-droplets/) - GPU Droplets have GPUs in a single or 8 GPU configuration, and they also come with two different kinds of storage\n* [1-Click Models](https://docs.digitalocean.com/products/marketplace/1-click-models/) - Deploy third-party generative AI models on GPU Droplets with no additional setup or configuration\n\n**Compute**\n* [Droplets](https://docs.digitalocean.com/products/droplets/) - On-demand Linux virtual machines\n* [Kubernetes](https://docs.digitalocean.com/products/kubernetes/) - Managed Kubernetes service\n* [App Platform](https://docs.digitalocean.com/products/app-platform/) - Platform-as-a-Service (PaaS) offering allowing users to build, deploy, and scale apps quickly while DigitalOcean manages the infrastructure, app runtime, and dependencies\n* [Functions](https://docs.digitalocean.com/products/functions/) - Serverless computing solution to run on-demand code\n\n**Data Services**\n* [Managed Databases](https://docs.digitalocean.com/products/databases/) - Fully-managed database cluster service \n    * [PostgreSQL](https://docs.digitalocean.com/products/databases/postgresql/)\n    * [MySQL](https://docs.digitalocean.com/products/databases/mysql/)\n    * [Kafka](https://docs.digitalocean.com/products/databases/kafka/)\n    * [MongoDB](https://docs.digitalocean.com/products/databases/mongodb/)\n    * [OpenSearch](https://docs.digitalocean.com/products/databases/opensearch/)\n    * [Valkey](https://docs.digitalocean.com/products/databases/valkey/)\n* [Vector Databases](https://docs.digitalocean.com/products/vector-databases/) - Managed clusters purpose-built for vector similarity search\n    * [Weaviate](https://docs.digitalocean.com/products/vector-databases/weaviate/)\n    * [OpenSearch](https://docs.digitalocean.com/products/vector-databases/opensearch/)\n    * [PostgreSQL](https://docs.digitalocean.com/products/vector-databases/postgresql/)\n* [Knowledge Bases](https://docs.digitalocean.com/products/knowledge-bases/) - Store, index, and retrieve data from various content sources\n\nNote: You should submit findings to us for MongoDB, Weaviate, Advanced Edition PostgreSQL, and Advanced Edition MySQL. \nFindings in Standard Edition PostgreSQL, Standard Edition MySQL, Valkey, Kafka, and OpenSearch should be submitted to [our partner, Aiven](https://bugcrowd.com/engagements/aiven-mbb-og).\n\n**Storage**\n* [Volumes Block Storage](https://docs.digitalocean.com/products/volumes/) - Network-attached block device that provides additional storage for Droplets\n* [Spaces Object Storage](https://docs.digitalocean.com/products/spaces/) - S3-compatible object storage including a built-in CDN\n* [Network File Storage](https://docs.digitalocean.com/products/nfs/) - Fully managed, POSIX-compliant file storage solution built for demanding workloads that provides scalable, high-throughput shared storage\n\n**Containers & Images**\n* [Snapshots](https://docs.digitalocean.com/products/snapshots/) - On-demand disk images of Droplets and volumes saved to your account\n* [Backups](https://docs.digitalocean.com/products/backups/) - Automatically-created disk images for Droplets\n* [SnapShooter](https://docs.digitalocean.com/products/snapshooter/) - A cloud backup and recovery solution\n* [Marketplace](https://docs.digitalocean.com/products/marketplace/) - Home for Droplet 1-Click Apps, Kubernetes 1-Click Apps, SaaS Add-Ons, and 1-Click Models from DigitalOcean and third-party vendors.\n    * Note: Marketplace third-party vendor apps are *not* in-scope for our program. \n* [Custom Images](https://docs.digitalocean.com/products/custom-images/) - Custom Linux or Unix-like images that you can import to DigitalOcean\n* [Container Registry](https://docs.digitalocean.com/products/container-registry/) - Private Docker image registry with additional tooling support\n\n**Networking**\n* [Domains and DNS](https://docs.digitalocean.com/products/networking/dns/) - DNS records managed from the DigitalOcean control panel, and can be integrated with Load Balancers and Spaces to streamline TLS certificate management\n    * Note: DigitalOcean is not a domain name registrar\n* [Reserved IPs](https://docs.digitalocean.com/products/networking/reserved-ips/) - Publicly-accessible static IP addresses that can be assigned to a Droplet\n* [Load Balancers](https://docs.digitalocean.com/products/networking/load-balancers/) - Fully-managed, highly available network load balancing service\n* [Cloud Firewalls](https://docs.digitalocean.com/products/networking/firewalls/) - Network-based, stateful firewall service for Droplets\n* [IPv6](https://docs.digitalocean.com/products/networking/ipv6/) - You can enable IPv6 on Droplets\n* [Virtual Private Cloud (VPC)](https://docs.digitalocean.com/products/networking/vpc/) - Logically isolated private network interface for cloud resources in the same account\n* [DDoS Protection](https://docs.digitalocean.com/platform/ddos-protection/) - Provides free, always-on protection from distributed denial-of-service (DDoS) attacks for applicable DO resources\n\n**Management**\n* [Cloud Security Posture Management (CSPM)](https://docs.digitalocean.com/products/cspm/) - Evaluates DO resources for misconfigurations and security risks, surfaces findings by severity, and provides guidance to help resolve them\n* [Monitoring](https://docs.digitalocean.com/products/monitoring/) - Free, opt-in service that gathers metrics about Droplet-level resource utilization\n* [Projects](https://docs.digitalocean.com/products/projects/) - Organize DO resources into groups that align with the applications, environments, and clients that you host\n* [Uptime](https://docs.digitalocean.com/products/uptime/) - Monitoring service that checks the health of any URL or IP address.\n\n**Platform**\n* [Accounts](https://docs.digitalocean.com/platform/accounts/) - On DigitalOcean, you manage your infrastructure and billing with teams. Your personal account on DigitalOcean lets you manage your team membership and your name, sign-in method, and email subscriptions.\n    * [2FA](https://docs.digitalocean.com/platform/accounts/2fa/) - Using two-factor authentication (2FA) on DigitalOcean adds an additional layer of security against unauthorized access to your account\n    * [SSH Keys](https://docs.digitalocean.com/products/droplets/how-to/add-ssh-keys/) - Manage SSH keys available to be provisioned onto Droplets\n* [Teams](https://docs.digitalocean.com/platform/teams/) - Teams are our account boundary. Someone in one team cannot manage resources in another team they are not a member of.\n    * Teams are comprised of owner, biller, member, modifier, and viewer roles with [different sets of permissions](https://docs.digitalocean.com/platform/teams/roles/).\n* [Organizations](https://docs.digitalocean.com/platform/organizations/) - Organizations are groupings of related teams. Organizations enable consolidated billing, payment, and invoicing, and provide detailed spend breakdowns by team. Organization owners can manage members, settings, and billing across teams in the organization, while team owners can manage their team’s resources and view spending.\n    * Organizations are comprised of owner, admin, and biller roles with [different sets of permissions](https://docs.digitalocean.com/platform/organizations/roles/predefined/). \n\n**Tools and Services**\n* [API](https://docs.digitalocean.com/reference/api/reference/) - DigitalOcean's public REST API\n    * [Granularly scope your API tokens](https://docs.digitalocean.com/reference/api/create-personal-access-token/) and check access control\n* [doctl](https://github.com/digitalocean/doctl) - The official command line interface for the DigitalOcean API\n* [do-agent](https://github.com/digitalocean/do-agent) - A daemon that collects system metrics from Droplets\n* [droplet-agent](https://github.com/digitalocean/droplet-agent) - A daemon that enables web console access on Droplets\n    * Note: These DO Github repos are *not* eligible for bounty rewards.\n\n\n**Feedback**\nWould you like to help us improve our program or have some feedback to share, please send your anonymous feedback here: [Program feedback link](https://go.intigriti.com/program-feedback)\nPlease note this form will be checked periodically and **should not** be used for submission or support queries.",
  "attachments": []
}
```

## Out of scope (version 2026-10-22 19:04 UTC)

```json
{
  "content": "**Submissions targeting resources or accounts owned by other DigitalOcean customers are out of scope.**\n\nAs a cloud provider, DigitalOcean owns a large IP space and nearly every report we receive in which attribution is solely based on IP address are out of scope reports on customers. For example, assets (e.g. random public DigitalOcean IPs or Spaces buckets with `*.digitaloceanspaces.com` domain) that Shodan or similar vulnerability scanners scan against are usually customers’ assets and thus are out of the scope of this program and should never be tested against. Public IPs belonging to AS14061(DigitalOcean, LLC) are usually assigned to DigitalOcean customers.\n\nPlease do not submit findings from automated scans unless you have verified and have high confidence that the vulnerable targets are part of DigitalOcean’s public infrastructure and have a demonstrated security impact. Repetitive submissions against DigitalOcean customers may result in expulsion from our program.\n\n# **Application-Specific Exclusions**\n\n1. **Third-Party Vulnerabilities:**  \n   1.1 Use of known vulnerable libraries/software without working proof of exploitability or impact.  \n2. **Information Disclosure:**  \n   2.1 Wordpress username disclosure.  \n   2.2 Verbose messages/files/directory listings without sensitive info.  \n   2.3 Banner grabbing/version disclosure.  \n3. **OAuth/Authentication Issues:**  \n   3.1 Pre-auth account takeover/OAuth squatting.  \n4. **Low-Impact Client-Side Vulnerabilities:**  \n   4.1 Self-XSS that cannot be used to exploit others.  \n5. **Cross-Origin Resource Sharing (CORS):**  \n   5.1 CORS Misconfiguration on non-sensitive endpoints.  \n6. **Cookie and Security Headers:**  \n   6.1 Missing cookie flags.  \n   6.2 Missing security headers.  \n7. **Cross-Site Request Forgery Issues:**  \n   7.1 Low/no impact CSRF attacks.  \n8. **Rate Limiting:**  \n   8.1 Bypassing rate-limits or the non-existence of rate-limits.  \n9. **Outdated Browsers:**  \n   9.1 Vulnerabilities affecting users with outdated/unpatched browsers (more than two versions behind).  \n10. **File Upload Issues:**   \n    10.1 Arbitrary file upload without proof of existence.  \n11. **Blind Server-Side Request Forgery (SSRF) in some circumstances:**  \n    11.1 Blind SSRF without proven business impact (e.g., pingbacks).  \n12. **Subdomain Issues:**  \n    12.1 Subdomain takeover without actual takeover.  \n13. **Metadata Handling Issues:**  \n    13.1 Not stripping metadata from files.  \n14. **Header Injection Vulnerabilities:**  \n    14.1 Host header injection without proven business impact.  \n15. **Outdated Domains & Static Links:**  \n    15.1 Links on static content referencing outdated third-party domains.  \n16. **Miscellaneous:**  \n    16.1 Clickjacking without proven impact or unrealistic user interaction.  \n    16.2 Double-Clickjacking.\n    16.3 Reverse tabnabbing.  \n    16.4 CSV injection.  \n    16.5 Autocomplete attribute on web forms.  \n    16.6 Non-invalidation of sessions (logout, enabling 2FA, etc.).  \n    16.7 Tokens leaked to third parties.  \n    16.8 Content injection without HTML modification.  \n    16.9 Email bombing.  \n    16.10 HTTP request smuggling with no proven impact.  \n    16.11 Homograph attacks.  \n    16.12 XMLRPC enabled.\n    16.13 Anything related to email spoofing, SPF, DMARC or DKIM.\n\n# **General Exclusions**\n\n17. **Publicly known processor Side-Channel Attacks:**  \n    17.1 The reason this rule exists is because there is no safe way to test without a special setup. If you have strong reason to believe that an issue may impact our environment, please contact us at security@digitalocean.com and we'll work with you to set up an environment for safe testing.  \n18. **Known Vulnerabilities:**  \n    18.1 If a reported vulnerability is already known through other means, it will be flagged as a duplicate.  \n19. **Theoretical Issues:**  \n    19.1 Security issues without realistic exploitation scenarios or requiring complex user interactions.  \n20. **Physical & Social Engineering Attacks:**  \n    20.1 Spam, social engineering, physical intrusion.  \n    20.2 Attacks needing physical access, man-in-the-middle, or compromised user accounts.  \n    20.3 Targeting DO employee workstations.\n21. **Denial of Service (DoS/DDoS):**  \n    21.1 DoS/DDoS attacks or brute force attacks.  \n22. **Outdated Software:**  \n    22.1 Vulnerabilities in software that no longer receive security updates.  \n    22.2 Reports stating software is outdated/vulnerable without proof of concept.  \n23. **Third-Party Vendor Vulnerabilities:**\n\t\t23.1 Vulnerabilities in upstream providers and open source software for which we are not the responsible maintainers (reportable but not bounty eligible).  \n24. **Zero-Day Vulnerabilities and CVEs:**  \n    24.1 Newly discovered zero-days and CVEs within 30 days of public patch release (reportable but not bounty eligible).\n25. **Third-party source of secrets, such as employee credentials**\n    25.1 We do not award bounty rewards for the reporting of leaked secrets unless there is a specific vulnerability in our platform (DO products or services) that lead to the secrets disclosure. If that is the case, please submit a report about that vulnerability instead. \n    25.2 You may email us at security@digitalocean.com to inform us about leaked secrets in credential lists or public databases. While this will not be awarded a bounty payout, we appreciate good faith notices and will investigate your claim.",
  "attachments": []
}
```

## Rules of engagement (version 2026-07-30 19:37 UTC)

```json
{
  "content": {
    "description": "#### By participating in this program, you agree to:\n\n* Respect the [Community Code of Conduct](https://go.intigriti.com/coc)\n* Respect the Intigriti [Terms and Conditions](https://go.intigriti.com/tac)\n* You may not participate in this program if you are ordinarily resident in, or located in, any country or region subject to comprehensive sanctions, or if you are an individual or entity identified on any applicable sanctions list (including those administered by OFAC, the EU, the UN, or the UK's OFSI).\n* Respect the scope of the program\n* Not discuss or disclose vulnerability information without prior written consent (including PoCs on YouTube and Vimeo)\n\n**Program Rules**\n*  While testing, please only test against your own accounts and resources. **Targeting DigitalOcean users or their resources (e.g. Droplets, Spaces, Databases, etc.) is NOT allowed.**\n*  You may NOT attempt to exfiltrate content from DigitalOcean without explicit advanced permission from DigitalOcean. You may never attempt to exfiltrate content from DigitalOcean customers.\n* Do not host personal or commercial applications on servers underneath your [@]intigriti.me DigitalOcean account.\n* While testing, we encourage (but do not require) you to include a custom HTTP header in all your requests.\n    * Providing such information will assist us with correlating your traffic to your research and expedite our ability to validate your report.\n* Please provide detailed reports with reproducible steps. If the report is not detailed enough to reproduce the issue, the issue will not be eligible for a bounty.\n* Multiple vulnerabilities caused by one underlying issue will be considered one issue.\n* When duplicates occur, we only award the first report that was received (provided that it can be fully reproduced).\n* Please help make a good faith effort to avoid privacy violations, destruction of data, or service degradation.\n\n\n**Validation times**\n\nWe will validate all submissions within the below timelines, once your submission has been verified by Intigriti.\n\nDigitalOcean will make a best effort to meet the following SLAs for hackers participating in our program.\nThe following SLAs are in business days (Mon-Fri) and may exclude days where there are regional holidays in the countries where our DigitalOcean staff are located.\n\n| Vulnerability Severity | Time to validate |\n| -------- | -------- |\n| Exceptional | 2 Working days |\n| Critical | 2 Working days |\n| High | 5 Working days |\n| Medium | 15 Working days |\n| Low | 15 Working days |\n\nWe'll do our best to keep you informed about our progress throughout the process.\n\n**Check our fix**\nWe offer a minimum **$50 bonus** to verify a resolved issue for us (when requested), and will gladly pay up to **10% of the total bounty** for a retest award when providing proof of comprehensive retest validation. \nTo receive a retest bonus, you are expected to validate whether any bypasses of the same vulnerability exist in the implemented fix. Related reports created after confirming a retest as fix complete may be marked as a Duplicate of the original issue.\nThis reward remains at the discretion of DigitalOcean to award.",
    "testingRequirements": {
      "intigritiMe": true,
      "automatedTooling": 10,
      "userAgent": "",
      "requestHeader": "X-BBP-Researcher: {Username}"
    },
    "safeHarbour": true,
    "createdAt": 1785440254
  },
  "attachments": []
}
```

## Severity assessment (version 2025-04-02 12:42 UTC)

```json
{
  "content": "DigitalOcean does not leverage CVSS for its severity assessment. Instead, we take a [contextual look](https://www.digitalocean.com/blog/digitalocean-security-debt) at impact and likelihood of a vulnerability and determine the commensurate risk to our business or customers between Informational, Low, Medium, High, or Critical. This means that you can be sure real, experienced security professionals are looking at all the details of your report to determine the severity and resulting bounty payment; you're not limited by what an algorithm dictates. When we triage issues, we will provide justification as to our severity decision if it differs from yours. Please note that our severity table ends at Critical. We will only consider Exceptional tier for truly monumental impact to the organization.\n\nWhen deciding what severity to set on your report, you may use CVSS, CWSS, SSVC, EPSS, or any other combination of tools to help you determine an accurate threshold. Please do not mark every issue a Critical/High severity unless you have reasonable justification for doing so.\n\nDigitalOcean will only issue monetary rewards for reports demonstrating meaningful impact. If DigitalOcean decides to offer a reward for a vulnerability report, the value of the reward will be based on the *impact and severity* of the reported vulnerability, to be determined by DigitalOcean in its sole discretion. Awards are granted entirely at the discretion of DigitalOcean.\n\nFor this reason, we **strongly** encourage researchers to spend extra time to provide a realistic attack/threat scenario adapted to our business. This will increase the chance of receiving a higher bounty.\n\nAt DigitalOcean's discretion, providing more complete research, proof-of-concept code, and detailed writeups may increase the bounty awarded. Conversely, DigitalOcean may pay less for vulnerabilities that require complex or over-complicated interactions for which the impact or security risk is negligible.",
  "attachments": []
}
```

## Bounty table (version 2024-11-06 15:50 UTC)

```json
{
  "currency": "USD",
  "bountyRows": [
    {
      "bountyRanges": [
        {
          "minScore": 0.1,
          "maxScore": 3.9,
          "minBounty": {
            "value": 100.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 450.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 4.0,
          "maxScore": 6.9,
          "minBounty": {
            "value": 700.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 1500.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 7.0,
          "maxScore": 8.9,
          "minBounty": {
            "value": 2000.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 4000.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 9.0,
          "maxScore": 9.4,
          "minBounty": {
            "value": 5000.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 8000.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 9.5,
          "maxScore": 10.0,
          "minBounty": {
            "value": 8000.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 10000.0,
            "currency": "USD"
          }
        }
      ],
      "bountyTierId": 3
    },
    {
      "bountyRanges": [
        {
          "minScore": 0.1,
          "maxScore": 3.9,
          "minBounty": {
            "value": 50.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 150.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 4.0,
          "maxScore": 6.9,
          "minBounty": {
            "value": 300.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 500.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 7.0,
          "maxScore": 8.9,
          "minBounty": {
            "value": 600.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 1500.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 9.0,
          "maxScore": 9.4,
          "minBounty": {
            "value": 1500.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 3000.0,
            "currency": "USD"
          }
        },
        {
          "minScore": 9.5,
          "maxScore": 10.0,
          "minBounty": {
            "value": 3000.0,
            "currency": "USD"
          },
          "maxBounty": {
            "value": 3000.0,
            "currency": "USD"
          }
        }
      ],
      "bountyTierId": 2
    }
  ],
  "rewardPolicy": null
}
```

## FAQ (version 2026-07-16 18:07 UTC)

```json
{
  "content": "### How can I create an account?\n\nYou can self-register on the application, but please don’t forget to use your `@intigriti.me` email address.\n\n* Please create dedicated testing accounts for any DO security research engagement. This allows our teams to know if any anomalous activity is associated with Intigriti or potential bad actors.\n* Please register a DigitalOcean account using your Intigriti `@intigriti.me` email.\n* Feel free to sign up normally for a new user account at [https://cloud.digitalocean.com/registrations/new](https://cloud.digitalocean.com/registrations/new) and you'll receive $5 of credit that doesn't expire (a valid credit card is still required to be linked to the account).\n* If you are testing with an account that does not use your Intigriti email address, we may take action against it for perceived malicious activity (account locks, bans, etc.)\n* Once you have finished testing, don’t forget to spin down resources to avoid any undue consumption.\n* Beyond the free trial offer, we will not provide credits or reimburse charges to researchers.\n\n### I think I found SSRF. How can I prove it?\n\nWe have set up an internal service you can try to hit to prove SSRF in our environment.\nThere are two endpoints you can try:\n\n- `https://ssrf-sheriff.internal.digitalocean.com/`\n- `https://ssrf-sheriff.s2r1.internal.digitalocean.com/`\n\nPlease include your Intigriti username in a `X-BBP-Researcher` header if you are able to control headers in your SSRF attempt, as well as include your username in a query parameter.\n\nIf your SSRF request is successful, you will receive a unique code to include in your report as proof of your success.\nIf you discover blind SSRF, the endpoint will trigger an alert for our Security team to validate against. Please include timestamp and IP information when you write up your report.\n\nDo NOT attempt SSRF exploits against any other internal resource without first receiving explicit permission from DigitalOcean.\n\n### What is a good learning resource for starting out on my bug bounty journey?\n\nThere are many excellent (free) resources available out there through [Portswigger](https://portswigger.net/web-security) and [OWASP](https://owasp.org/www-project-juice-shop/). \n\nA recently released, educational training resource that we particularly like is the [Wiz Bug Bounty Masterclass](https://www.wiz.io/bug-bounty-masterclass)! Pay special attention to their section on [AI & Bug Bounty](https://www.wiz.io/bug-bounty-masterclass/foundations/ai-bug-bounty), and using *The \"Human in the Loop\" Approach* for how to provide the most value in your reports, if using AI tools.\n\n### What is a good resource for researcher's AI tools to understand DO?\n\nPlease review the above regarding *The \"Human in the Loop\" Approach* that has proven to be most valuable for discovering vulnerabilities with the *help* of LLMs. \nFor your AI tools, agents can review https://docs.digitalocean.com/llms.txt found at https://docs.digitalocean.com/reference/mcp/.",
  "attachments": []
}
```
