# Doctolib (YesWeHack) - raw policy

- Source: https://api.yeswehack.com/programs/doctolib-public-bug-bounty-program
- Policy last updated: 2026-07-17T10:14:17+02:00
- Bounty: True | VDP: False | Public: True | Max reward: 50000
- Required user agent: BugBounty/42 (YWH)
- Report submission cost: 10

## In scope

| Scope | Type | Value |
| --- | --- | --- |
| `www.doctolib.(fr|de|it)` | Web application | MEDIUM |
| `pro.doctolib.(fr|de|it) (see "Free features for healthcare professionals"))` | Web application | MEDIUM |
| `Special scenarios (see description)` | Web application | CRITICAL |
| `*.doctolib.(fr|de|it|com|net)` | Web application | LOW |
| `https://apps.apple.com/fr/app/doctolib/id925339063` | Mobile application IOS | LOW |
| `http://play.google.com/store/apps/details?id=fr.doctolib.www` | Mobile application Android | LOW |
| `*.siilo.com` | Application | MEDIUM |
| `https://apps.apple.com/ie/app/doctolib-siilo/id1083002150` | Mobile application IOS | MEDIUM |
| `https://play.google.com/store/apps/details?id=com.siilo.android&hl=en` | Mobile application Android | MEDIUM |

## Out of scope

- Note: should you discover a critical issue within an asset that falls outside the program's scope, we would appreciate it and may choose to offer a reward at our discretion.
- community.doctolib.com | .fr | .de | .it
- info.doctolib.com | .fr | .de | .it
- status.doctolib.com | .fr | .it
- store.doctolib.com
- media.doctolib.com
- fb.doctolib.com | fb-dev.doctolib.fr
- pro-app.doctolib.com
- developers.doctolib.com
- dmp.doctolib.fr | dmp-prd-aws-*.doctolib.fr
- fm.doctolib.fr | fm.doctolib.it | voip.doctolib.de and other decommissioned / dangling Doctolib sub-domains
- doctocommit.doctolib.fr
- share.doctolib.net
- doctolib.atlassian.net and any *.atlassian.net path
- doctolib.zendesk.com | siilo.zendesk.com
- api.tanker.io (Accessing the tanker private key is normal functioning of the Tanker protocol)
- There is no IDOR on /api/security/tanker_groups via subject_id
- exceptions.doctolib.fr | .de
- billing-client-logs.billing.doctolib.fr | api-external.datascience.doctolibdata.com
- doctolib-ps-ehr-downloads.s3.amazonaws.com
- vettore.it and any related Vettore assets
- Craft CMS on www.siilo.com, plus siilo.com marketing / staging sub-domains (l.siilo.com, l-dev.siilo.com, web.siilo.com, web-dev.siilo.com, www-admin.siilo.com, mjt-dev.siilo.com, att-dev-nl.siilo.com, sandbox-nl.siilo.com, connect.siilo.com, prod-nl-web.siilo.com)
- Third-party assets linked from our products (e.g. login.decathlon.net, wallet.esw.esante.gouv.fr, preprod.alaxione.fr, hooks.zapier.com, cron.signitic.app, job-boards.greenhouse.io, docto.digitalstack.it, and any hospital-specific or customer-specific host)
- Any *.sslip.io, *.nip.io, AWS ELB / load-balancer hostname, or raw IPv4 / IPv6 address
- Look-alike, typo-squatting or expired domains not owned by Doctolib (e.g. www.dioctolib.de, doctolib.fr.evil.com, doctodketest.tk, doctolib-poc.partner-experience.com)
- Public GitHub repositories we do not own (such as student projects doing)

## Qualifying vulnerabilities

- Authentications Bypass
- Authorizations Bypass
- Insecure direct object references (IDOR)
- Business logic flaws
- Stored / Reflected Cross Site Scripting (XSS)
- SQL Injections (SQLi)
- Remote code execution (RCE)
- Local files access and manipulation (LFI, RFI, XXE, SSRF, XSPA)
- Open redirect
- CORS with real security impact
- Personal Data Leakage
- Healthcare Data Leakage
- Secret Data Leakage
- Passive user enumeration (one request allows you to list users without privileges)
- Ability to find the account_id of another non-relative account for a given email/phone (fixed reward: 200€)

## Non-qualifying vulnerabilities

- Basically anything that is reported by passive or active automated scanners. We already run this kind of tools.
- Credentials leak
- Any vulnerability that will disclose public information
- Any hypothetical flaw or best practice without exploitable Proof of Concept.
- Reports of security issues already known and tracked by the Doctolib Security team.
- Reports of missing “best practices” or other guidelines which do not indicate a security issue.
- Attacks related to email servers, email protocols, email security (e.g., SPF, DMARC, DKIM) or email spam.
- Security issues in third-party applications, services, or dependencies that integrate with Doctolib products or infrastructure that do not have a demonstrable proof of concept for the vulnerability (e.g. libraries, SaaS services).
- Attacks designed or likely to degrade, deny, or adversely impact services or user experience (e.g. denial of service, distributed denial of service, brute force, password spraying, spam...)
- Performing physical, social engineering, or electronic attacks against Doctolib personnel, offices, wireless networks, or property
- Missing cookie flags on non-sensitive cookies
- "Self" XSS
- Account enumeration
- Missing HTTP headers (e.g. lack of HSTS)
- Reports of insecure SSL/TLS ciphers (unless accompanied with working proof of concept)
- Mixed content warnings
- "HTTP Host Header" XSS
- Clickjacking/UI redressing/TapJacking
- Insufficient session expiration
- Software version disclosure
- Recently disclosed 0-day vulnerabilities
- Presence of autocomplete attribute on web forms
- Vulnerabilities affecting outdated browsers or platforms
- Issues that require physical access to a victim’s computer/device
- Missing CAPTCHA/RateLimit on info.doctolib.(fr|de|it)
- Exploits that are only possible on Android version 9.x and below
- Exploits that are only possible on IOS version 12.x and below
- Exploits that are only possible on a jailbroken device
- Lack of code obfuscation
- Lack of binary protection
- Jailbreak and root detection
- Crashing your own application
- Testing for weak credentials
- Lack of rate limiting (unless it has a significant impact)
- API key stored on HTTP client side with no demonstrated impact
- Ability to retrieve or bypass the booking code to book an appointment
- Ability to book an appointment with a doctor that blocked a patient

## Reward grids (EUR)

- reward_grid_default: {"bounty_low": 100, "bounty_medium": 500, "bounty_high": 1500, "bounty_critical": 5000}
- reward_grid_very_low: {"bounty_low": null, "bounty_medium": null, "bounty_high": null, "bounty_critical": null}
- reward_grid_low: {"bounty_low": 100, "bounty_medium": 500, "bounty_high": 1500, "bounty_critical": 5000}
- reward_grid_medium: {"bounty_low": 100, "bounty_medium": 500, "bounty_high": 4000, "bounty_critical": 20000}
- reward_grid_high: {"bounty_low": null, "bounty_medium": null, "bounty_high": null, "bounty_critical": null}
- reward_grid_critical: {"bounty_low": 100, "bounty_medium": 500, "bounty_high": 4000, "bounty_critical": 50000}

- Systemic issue rule: {"level1": 100, "level2": 100, "level3": 25, "level4": 0, "level5": 0, "level6": 0}

## Account access

You can create your own test account on : [https://www.doctolib.fr/sessions/new](https://www.doctolib.fr/sessions/new)

You can use your YesWeHack email alias (@yeswehack.ninja) to register; you will find it in your [MyYesWeHack menu](https://yeswehack.com/user/my-yeswehack/email-alias)

## Rules (verbatim)

# Introduction

Welcome to the Doctolib Bug Bounty program! We're excited to offer a way for the security community to help us find and fix vulnerabilities on our platform.
  
Our mission, as a leading healthcare service provider in Europe, is to ensure the utmost confidentiality, integrity, and availability of our users' data. We are proud to invite skilled hunters to assist us in identifying vulnerabilities and strengthen the security of our platform.

We are dedicated to collaborating with the most brilliant minds in the industry to detect potential security gaps and to remain ahead of emerging threats. Our bug bounty program is a crucial element of our security strategy, and we are thrilled to make it available to the public.

Thank you for your consideration of our program. If you have any questions contact us at security@doctolib.com

# ☑️ Eligibility and Rules

To ensure the safety and security of all parties involved, we have established the following cumulative eligibility rules for our bug bounty program:

- You must be the initial discoverer of a vulnerability and the vulnerability must not have been previously detected in our internal vulnerability tracking system.
- The vulnerability must be reported exclusively through our designated reporting platform, yeswehack.com.
- The report should include a clear textual description of the vulnerability, a step-by-step procedure to reproduce the issue, and any necessary attachments such as screenshots or proof of concept code.
- The report should also include a clear explanation of the impact of the vulnerability's exploitation.
- You must comply with the testing precautions.
- No phishing on users and employees.
- All testing made under the Doctolib Bug Bounty program must not have any negative impact on the care team or patients, in accordance with the “testing precautions” below.
  
Failure to comply with the preceding rules will result in the rejection of your report.

# 💵 Reward

We consider that spotting big bugs requires big rewards. For this reason, we propose a specific and detailed reward structure to ensure that there is no confusion or ambiguity in the allocation of the rewards. 

-   Personal data typology defines 5 typologies of data.
-   The reward grid offer rewards based on the typology of the data and the business impact 

## Personal data typology
We have developed an in-house system for categorizing personal data based on its level of sensitivity and re-identification risk. This system enables us to precisely assess the severity of any vulnerability identified, and ensure that our bug bounty program rewards are tailored to the level of risk posed by the vulnerability. 

| GDPR classification                               | Bug Bounty typology | Description and example                                                                                                                                                                                                                                                                                  |
|---------------------------------------------------|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Personal Information                              | Type 1              | Data with a low risk of re-identification:<br>- technical IDs<br>- pseudonymized data                                                                                                                                                                                                                    |
| Personal Information                              | Type 2              | Data where medium identification needs an external data:<br>- IP address<br>- phone number<br>- personal address                                                                                                                                                                                       |
| Personal Information                              | Type 3              | Data with an indisputable risk of re-identification<br>- first name and last name<br>- email address                                                                                                                                                                                                    |
| Personal Health Information                       | Type 4              | Data that can provide information insights into a person's health status (e.g.: appointments data)                                                                                                                                                                                                      |
| Personal Health Information<br>(and any other “special category of data” as defined in GDPR Article 9) | Type 5              | Any information that is collected about a person's health status, such as their vital signs, test results, and medical diagnoses.<br>This information is typically collected by healthcare providers and is used to diagnose and treat medical conditions, monitor treatment effectiveness, and track disease progression. |


## 🎯 The reward grid
This reward grid has been designed to provide clear guidelines on the types of vulnerabilities we are interested in, and the corresponding rewards for each. If you have any questions about our reward grid, we encourage you to ask for clarification by email.  

| Exploit (category)         | Exploit (detail)                                            | Impact on Doctolib’s users (pro and patient):<br /> Group of users (ex: one http request to access several non-relative users) | Impact on Doctolib’s users (pro and patient):<br /> Any single given user account randomly chosen (ex: IDOR that require to do a HTTP request for each user) |
|-------------------------------------------------------|------------------------------------------------------|---------------------------------------------------------------------------|--------------------------------------------------------------|
| Access to PII                                         | Access to "type 1" data                              | Medium                                                                    | Low                                                           |
| Access to PII                                         | Access to "type 2" data                              | High                                                                      | High                                                          |
| Access to PII                                         | Access to "type 3" data                              | High                                                                  | High                                                          |
| Access to PII                                        | Access to "type 4" data                              | Critical                                                                  | Critical                                                      |
| Access to PII                                         | Access to "type 5" data                              | Critical (sp. scenario)                                                   | Critical                                                      |
| Manipulate our Patient app to send emails from Doctolib server | Sophisticated (ex: insert images in Doctolib emails)                     | High                                                          | Medium (possibly high at our discretion)                  |
| Manipulate our Patient app to send emails from Doctolib server | Simple link                                          | High                                                                      | Medium                                                        |
| Manipulate our Patient app to send SMS from "Doctolib"        | Full control of the content                                               | High                                                          | High                                                          |
| Manipulate our Patient app to send emails from Doctolib server       | Link injection                                       | High                                                                      | High                                                          
| Cross-site scripting     | Access to DOM with user action required (ex: reflected xss)                                        | High                                                                      | Medium                                                          |

Note that the display of healthcare professional data (such as professional phone number) is normal functioning of our product. As mentioned in our Privacy Policy, Doctolib uses specialized service providers to feed its public directory (see our privacy policy on this matter: https://info.doctolib.fr/politique-de-protection-des-donnees-personnelles/).


## 💰The special scenario
Special bonuses are the most important reward for security vulnerabilities that pose a significant risk to our platform and cause us significant concern. If your critical vulnerability fall under any of the following scenario, you will be rewarded with : 

## 50 000 € 
(instead of 20 000€)

### 🚨The “game over” scenario
Ability to gain privileges on any production instance of our Ruby on Rails monolith, to read or write the production environment variable "SECURITY_BUG_BOUNTY_DOCTOLIB_IS_PWN," which contains the URL of a webhook that triggers a security crisis. RCE in other infrastructure components do not qualify as a "game over" scenario.

### 🎯The “One shot” scenario
Ability to use vulnerability at the application level to dump the entire patient base of any given Doctor (ex: export of the patient base of any doctor randomly chosen) with a reasonably small amount of request (ex: IDOR that allows to extract a partial amount of the patient base fall under regular “critical”). 


Please note that our detection rules are not designed to filter out bug bounty user agents, as we believe that would be unfair. We encourage all participants to follow our testing precautions below and to act in an ethical and responsible manner.
  

# ⛑ Testing precautions
We ask that you conduct your bug bounty activities in a way that does not impact the experience of our care teams or patients. If you are interested in testing something that may be considered dangerous, we encourage you to contact us by email, and we will work with you to provide the necessary testing conditions. 

🧑‍⚕️If you want to test appointment booking, do not use your real Doctolib account. Please 

-   DON'T use your Doctolib personal account. Please create a test account with fake data. The firstname, lastname, birthdate, phone and email will be in the patient base of this test Doctor and security researcher from our private bug bounty will be able to access it.
-   make an appointment with our [fake doctor](https://www.doctolib.fr/medecin-generaliste/levallois-perret/albertus-boulenfunkierchenblah-levallois-perret).
- The code to book an appointment with Dr Albertus Boulenfunkierchenblah is 42

We strive to provide optimal testing conditions (e.g. no VPN required) but failure to adhere to the stated precautions and causing business issues will result in disqualification from the bug bounty program without reward.

TLDR;
-   Use the "BugBounty/42 (YWH)" string to the user-agent (or read the exception below)
-   Avoid using automated tools, or use them the gentle way (Max 10 requests per second).

Our applications are supposed to be hardened, so you should be able to perform scans. We only ask you to add the "BugBounty/42 (YWH)" string to the user-agent header in your requests.  This is important because in case your traffic has an impact on the quality of our services, we will temporarily block the bug bounty requests based on this user agent.

## User agent exemption 
The specific user agent is required for heavy traffic. However, for lighter traffic when searching for bugs, it is acceptable to temporarily use a regular user agent if you believe it has an impact on your research. This must remain exceptional.

# 📣 Communication and Feedback
We encourage all hunters to report any vulnerabilities they find in our system, and we provide clear channels for communication and feedback. If you believe you have discovered a vulnerability, we recommend that you report it through the YesWeHack platform, where we run our bug bounty program.

You can contact us by email at security@doctolib.com for any reason, such as requesting testing conditions or asking for clarification on our program rules.
  

### 😇 ETHICS
-   You must not leak, manipulate, or destroy any user data.
-   You must not be a former or current employee of Doctolib or one of its contractors.
-   No vulnerability disclosure, including partial is allowed.

#### Free features for healthcare professionals

Certain features of Doctolib Pro are free and require regular identity verification (for example, the Siilo app). These features are within the scope of this public bug bounty program.

Other free features require verification of the right to practice through a government-issued ID document (e.g., Carte Professionnelle de Santé). These features are outside the scope of this public bug bounty program.

# Hints

Here, you'll find some explanations regarding the business logic behind certain features. These explanations are provided to help you save time during your research, giving you a clearer focus.

## Medical Data Synchronization process 

The medical data synchronization process is about updating appointment data or patient messaging data in order to link them an account. Here’s what you need to know:

- Offline Appointments / patient messaging:
	- These are appointments or patient messaging directly created by the doctor and aren’t connected to any online user account.
	- The goal of the synchronization process is to link the offline data to an account.
- Relative Appointments / patient messaging:
	- When a user (= a caregiver) books an appointment or send a patient messaging for someone else (= a relative). The appointment / patient messaging are linked to the online account of the caregiver but not yet to the one of the relative.
	- The goal of the synchronization process is to link the relative data to the account of the relative.

The email and/or phone number given at the time of the appointment booking or the patient messaging creation will get a link. Clicking this link starts the synchronization process. Here are the requirement to successfully pass the synchronisation process:
- You need to have access to the email and/or phone number tied to the appointment / patient messaging. For appointment only, if there’s no email, then only the phone number matters and you need to know the 3 first letter of the patient name. The phone number (and the email if not empty) must match with the user account.
- For relative appointment / patient messaging, the identity data tied to the appointment / patient messaging must match with the account of the relative. This includes first name, last name, and date of birth. Please note that the identity match is here to prevent accidental synchronization but the ability to brute-force the identity will not be rewarded.


## Here is a hash for the record
1b46d17e91790a31842ba5f9977c72356abbde2b8e93a0aef92f556bc5e78eab
