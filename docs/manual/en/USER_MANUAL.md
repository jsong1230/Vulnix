# Vulnix User Manual

**Version**: 1.0
**Last Updated**: February 2026

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Repository Integration](#2-repository-integration)
3. [Security Scanning](#3-security-scanning)
4. [Vulnerability Management](#4-vulnerability-management)
5. [Automated Patch PRs](#5-automated-patch-prs)
6. [Security Dashboard](#6-security-dashboard)
7. [False Positive Management](#7-false-positive-management)
8. [Notifications](#8-notifications)
9. [CISO Reports](#9-ciso-reports)
10. [VS Code Extension](#10-vs-code-extension)
11. [API Key Management](#11-api-key-management)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Getting Started

### 1.1 What is Vulnix?

Vulnix is a developer-focused security agent SaaS that automatically detects security vulnerabilities in your code repositories and generates patch pull requests — all without manual intervention.

**Core capabilities:**
- Two-stage detection engine combining Semgrep (rule-based SAST) and Claude AI (LLM-based analysis) to minimize false positives
- Automatic scanning triggered by PR creation or branch pushes, with results delivered within minutes
- AI-generated patch code submitted as pull requests for each detected vulnerability
- Vulnerability classification based on OWASP Top 10 with CWE mapping
- Real-time security score tracking per repository and team
- Slack and Microsoft Teams notifications
- Automated CISO report PDF generation for CSAP, ISO 27001, and ISMS compliance
- Real-time vulnerability highlighting in VS Code as you write code

**Supported languages:** Python, JavaScript, TypeScript, Java, Go

---

### 1.2 Sign Up and Log In (GitHub OAuth)

Vulnix uses GitHub OAuth for authentication — no separate account registration required.

**Login steps:**

1. Navigate to `https://app.vulnix.dev`.
2. Click the **"Sign in with GitHub"** button on the main page.
3. You will be redirected to GitHub's OAuth authorization page.
4. Review the permissions requested by Vulnix and click **"Authorize vulnix"**.
5. After authorization, you will be automatically redirected to the Vulnix dashboard.

> **Note:** A personal team is automatically created on your first login. To invite teammates, go to Settings > Team Management and send email invitations.

**Direct API call (reference):**
```bash
# Exchange GitHub OAuth code for a JWT token
curl -X POST https://api.vulnix.dev/api/v1/auth/github \
  -H "Content-Type: application/json" \
  -d '{"code": "github_oauth_code_here"}'
```

---

### 1.3 Connecting Your First Repository (GitHub)

When you first access the dashboard after login, you will see a repository connection guide.

**Steps to connect a GitHub repository:**

1. Click the **"Add Repository"** button at the top of the dashboard.
2. Select the **"GitHub"** tab.
3. Click **"Install GitHub App"** to be redirected to the GitHub App installation page.
4. Choose the repositories you want to analyze (or all repositories) and click **"Install"**.
5. After returning to Vulnix, a list of accessible repositories will be displayed.
6. Click the **"Connect"** button next to the repository you want to add.
7. Once connected, an initial full scan will start automatically.

> **Tip:** The initial scan may take 5 to 15 minutes depending on repository size. You can monitor scan progress under Dashboard > Scan History.

---

## 2. Repository Integration

### 2.1 Connecting a GitHub Repository

Vulnix integrates with GitHub using the GitHub App method, which uses Installation Tokens rather than OAuth tokens. This means no token expiration to worry about and a more stable connection.

**Steps:**
1. Click **Repositories** in the left sidebar of the dashboard.
2. Click the **"Add Repository"** button in the upper right.
3. Under the GitHub tab, click **"Install GitHub App"**.
4. After installing the app, select the repository you want to connect and click **"Connect"**.

**API example:**
```bash
# List connected repositories
curl -X GET "https://api.vulnix.dev/api/v1/repos?platform=github" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Register a repository
curl -X POST "https://api.vulnix.dev/api/v1/repos" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "github_repo_id": 123456789,
    "full_name": "my-org/my-repo",
    "default_branch": "main",
    "language": "Python",
    "installation_id": 987654
  }'
```

---

### 2.2 Connecting a GitLab Repository (Personal Access Token)

GitLab integration uses a Personal Access Token (PAT). Your token is encrypted before being stored.

**How to generate a PAT:**
1. Go to your GitLab account settings > Access Tokens.
2. Enter a token name and select the `read_repository`, `write_repository`, and `api` scopes.
3. Set an expiration date and click **"Create personal access token"**.
4. Copy the generated token (it will not be shown again).

**Steps to connect in Vulnix:**
1. In the Add Repository dialog, select the **GitLab** tab.
2. Enter your **GitLab instance URL** (e.g., `https://gitlab.com` or a self-hosted URL).
3. Enter your **Personal Access Token**.
4. Click **"Load Projects"** to see a list of accessible projects.
5. Select the project you want to connect and click **"Connect"**.

**API example:**
```bash
# List GitLab projects
curl -X GET "https://api.vulnix.dev/api/v1/repos/gitlab/projects?access_token=glpat-xxxx&gitlab_url=https://gitlab.com" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Register a GitLab repository
curl -X POST "https://api.vulnix.dev/api/v1/repos/gitlab" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gitlab_project_id": 12345678,
    "full_name": "my-group/my-project",
    "default_branch": "main",
    "language": "Python",
    "gitlab_url": "https://gitlab.com",
    "access_token": "glpat-xxxxxxxxxxxx"
  }'
```

> **Security note:** Your PAT is stored using AES-256 encryption and will never be displayed in plain text.

---

### 2.3 Connecting a Bitbucket Repository (App Password)

Bitbucket integration uses an App Password, which is safer than using your account password directly.

**How to create an App Password:**
1. Go to your Bitbucket account settings > App passwords.
2. Click **"Create app password"**.
3. Enter a label and check the `Repositories: Read` and `Webhooks: Read and write` permissions.
4. Click **"Create"** and copy the generated App Password.

**Steps to connect in Vulnix:**
1. In the Add Repository dialog, select the **Bitbucket** tab.
2. Enter your **Bitbucket username** and **App Password**.
3. Enter your **Workspace name** and click **"Load Repositories"**.
4. Select the repository and click **"Connect"**.

**API example:**
```bash
# List Bitbucket repositories
curl -X GET "https://api.vulnix.dev/api/v1/repos/bitbucket/repositories?username=myuser&app_password=ATBB-xxxx&workspace=my-workspace" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Register a Bitbucket repository
curl -X POST "https://api.vulnix.dev/api/v1/repos/bitbucket" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "my-workspace",
    "repo_slug": "my-repo",
    "full_name": "my-workspace/my-repo",
    "default_branch": "main",
    "language": "JavaScript",
    "username": "myuser",
    "app_password": "ATBB-xxxxxxxxxxxx"
  }'
```

---

### 2.4 Disconnecting a Repository

Disconnecting a repository will permanently delete all associated scan data and vulnerability records. This action cannot be undone.

**Steps to disconnect:**
1. In the dashboard, click on the repository you want to disconnect.
2. Click the **"More options (...)"** menu in the upper right of the repository detail page.
3. Select **"Disconnect"**.
4. In the confirmation dialog, type the repository name and click **"Disconnect"**.

> **Permissions:** Only users with the `owner` or `admin` role in the team can disconnect repositories.

**API example:**
```bash
curl -X DELETE "https://api.vulnix.dev/api/v1/repos/{repo_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 3. Security Scanning

### 3.1 Automatic Scan Triggers (PR Creation / Branch Push)

When you connect a repository, Vulnix automatically registers webhooks on GitHub, GitLab, or Bitbucket. Scans are then triggered automatically on the following events.

**Automatic trigger events:**

| Platform | Trigger Events |
|---|---|
| GitHub | PR creation, branch push, PR update |
| GitLab | Push, merge request creation/update |
| Bitbucket | Push, pull request creation/update |

**Scan workflow:**
1. Code change detected (webhook received)
2. Changed files extracted
3. Semgrep static analysis executed (rule-based first-pass detection)
4. Claude AI analysis executed (LLM-based second-pass verification and false positive filtering)
5. Vulnerabilities stored and severity classified
6. Patch code generated and submitted as a PR
7. Slack/Teams notification sent (if configured)

---

### 3.2 Running a Manual Scan

You can manually trigger a scan on any repository at any time.

**Triggering a manual scan from the UI:**
1. Select the repository you want to scan from the dashboard.
2. On the repository detail page, click the **"Scan Now"** button.
3. Choose the branch to scan and click **"Start Scan"**.

**API example:**
```bash
# Trigger a manual scan
curl -X POST "https://api.vulnix.dev/api/v1/scans" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "branch": "main",
    "commit_sha": "abc123def456"
  }'

# Example response
{
  "success": true,
  "data": {
    "id": "scan-job-uuid",
    "status": "queued",
    "repo_id": "repo-uuid",
    "trigger": "manual",
    "branch": "main",
    "created_at": "2026-02-26T10:00:00Z"
  }
}
```

> **Note:** If a scan is already in progress for the same repository, a new scan will not be started (409 Conflict response).

---

### 3.3 Checking Scan Progress

**From the UI:**
1. Click **Scans** in the left sidebar.
2. Review the status of each scan in the scan list.

**Scan status values:**

| Status | Description |
|---|---|
| `queued` | Scan is waiting to start |
| `running` | Scan is currently in progress |
| `completed` | Scan finished successfully |
| `failed` | Scan encountered an error |
| `cancelled` | Scan was cancelled |

**API example:**
```bash
# Get the status of a specific scan
curl -X GET "https://api.vulnix.dev/api/v1/scans/{scan_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 3.4 Supported Languages and Vulnerability Types

**Supported languages:**
- Python (3.6+)
- JavaScript (ES6+)
- TypeScript
- Java (8+)
- Go (1.16+)

**Detected vulnerability types (OWASP Top 10):**

| Vulnerability Type | Examples |
|---|---|
| SQL Injection | Non-parameterized queries, ORM bypass |
| Cross-Site Scripting (XSS) | Unvalidated user input rendered as HTML |
| Broken Authentication | Weak password policies, missing JWT validation |
| Sensitive Data Exposure | Hardcoded passwords, exposed API keys |
| Security Misconfiguration | Debug mode enabled, misconfigured CORS |
| Insecure Deserialization | Unsafe use of `pickle`, `yaml.load()` |
| Path Traversal | Unvalidated file path parameters |
| Command Injection | Unvalidated input passed to `os.system()`, `subprocess` |
| SSRF | Unvalidated URL parameters used in outbound requests |
| Cryptographic Issues | MD5/SHA1 usage, weak encryption keys |

---

## 4. Vulnerability Management

### 4.1 Viewing the Vulnerability List (Severity / Status Filters)

**From the UI:**
1. Click **Vulnerabilities** in the left sidebar.
2. Use the filter panel at the top to narrow down results.

**Available filters:**

| Filter | Options |
|---|---|
| Severity | `critical`, `high`, `medium`, `low` |
| Status | `open`, `fixed`, `false_positive`, `accepted_risk` |
| Repository | Select a specific repository |
| Vulnerability Type | `sql_injection`, `xss`, `path_traversal`, etc. |

**API examples:**
```bash
# List vulnerabilities (filtered by critical severity)
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities?severity=critical&status=open&page=1&per_page=20" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# List vulnerabilities for a specific repository
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities?repo_id={repo_id}&severity=high" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 4.2 Viewing Vulnerability Details (Code Location, CWE/OWASP Classification)

Click on any vulnerability in the list to open its detail page.

**Information included on the detail page:**
- **Description:** A natural language explanation of the vulnerability
- **Code location:** File name, line number, and code snippet
- **Severity:** Critical / High / Medium / Low
- **CWE classification:** CWE ID such as CWE-89 (SQL Injection)
- **OWASP classification:** OWASP Top 10 category such as A03:2021
- **AI analysis:** Claude AI's assessment and recommended remediation
- **Linked patch PR:** Link to the auto-generated patch PR (if available)

**API example:**
```bash
# Get vulnerability details
curl -X GET "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 4.3 Updating Status: open / fixed / false_positive / accepted_risk

You can manually update the status of any vulnerability.

**Status definitions:**

| Status | Meaning |
|---|---|
| `open` | Unresolved (default) |
| `fixed` | Remediation complete |
| `false_positive` | Determined to be a false alarm |
| `accepted_risk` | Risk acknowledged and intentionally accepted |

**Updating status from the UI:**
1. Select a vulnerability from the list or detail page.
2. Choose the desired status from the status dropdown.
3. Enter a reason for the change and click **"Save"**.
4. The repository's security score is recalculated immediately after the status change.

**API examples:**
```bash
# Update vulnerability status
curl -X PATCH "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "fixed"
  }'

# Mark as false positive and auto-register a pattern
curl -X PATCH "https://api.vulnix.dev/api/v1/vulnerabilities/{vuln_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "false_positive",
    "create_pattern": true,
    "file_pattern": "tests/**",
    "pattern_reason": "Intentional pattern in test fixtures"
  }'
```

---

### 4.4 Marking Vulnerabilities as False Positives

When you mark a vulnerability as a false positive, Vulnix automatically filters out similar findings in future scans.

**How to mark a false positive:**
1. On the vulnerability detail page, click **"Mark as False Positive"**.
2. Enter a reason (e.g., "Intentional pattern in test code").
3. Enable **"Auto-register false positive pattern"** to automatically add the Semgrep rule ID and file pattern to the team's false positive registry.
4. If you don't specify a file pattern, Vulnix will infer one from the vulnerability's file path directory.

---

## 5. Automated Patch PRs

### 5.1 Viewing Patch PRs

After detecting a vulnerability, Claude AI automatically generates patch code and submits a pull request to your repository.

**From the UI:**
1. Click **Patches** in the left sidebar.
2. Browse the list of generated patch PRs.
3. Use the status filter to view `created`, `merged`, `closed`, or `rejected` PRs.

**Patch PR list information:**
- PR number and title
- Linked vulnerability
- PR status (created / merged / closed / rejected)
- Creation timestamp

**API examples:**
```bash
# List patch PRs
curl -X GET "https://api.vulnix.dev/api/v1/patches?status=created&page=1&per_page=20" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# List patch PRs for a specific repository
curl -X GET "https://api.vulnix.dev/api/v1/patches?repo_id={repo_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 5.2 Reviewing and Approving Patch Code

1. On the patch PR detail page, click the **"View on GitHub"** link.
2. Review the changed code on the GitHub PR page.
3. If the patch looks appropriate, click **"Merge pull request"** to merge it.
4. Once the patch is merged, Vulnix automatically updates the associated vulnerability status to `fixed`.

> **Important:** Always review auto-generated patch code before merging. AI-generated patches may not align perfectly with your business logic.

---

### 5.3 Requesting a Patch Regeneration

If an auto-generated patch is not suitable, you can request a new one.

**From the UI:**
1. On the patch PR detail page, click the **"Regenerate Patch"** button.
2. Optionally provide additional context or instructions.
3. Click **"Regenerate"** to create a new patch PR.

**API example:**
```bash
# Get patch PR details (includes vulnerability info)
curl -X GET "https://api.vulnix.dev/api/v1/patches/{patch_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 6. Security Dashboard

### 6.1 How the Security Score is Calculated

The Vulnix security score is calculated based on the number of vulnerabilities in `open` status.

**Formula:**
```
Security Score = max(0, 100 - (critical × 25 + high × 10 + medium × 5 + low × 1))
```

**Example:**
- 1 Critical, 2 High, 3 Medium → `100 - (25 + 20 + 15)` = **40 points**
- 0 vulnerabilities → **100 points (perfect score)**

**Score grades:**

| Score Range | Grade | Meaning |
|---|---|---|
| 90 – 100 | A (Excellent) | Strong security posture |
| 70 – 89 | B (Good) | Some improvements recommended |
| 50 – 69 | C (Fair) | Active remediation needed |
| 0 – 49 | D (Poor) | Immediate action required |

---

### 6.2 Checking Security Scores by Repository

**From the UI:**
1. The dashboard home page shows all connected repositories with their security scores.
2. Click on any repository to view its detailed score and vulnerability breakdown.

**API example:**
```bash
# Get a repository's security score
curl -X GET "https://api.vulnix.dev/api/v1/repos/{repo_id}/score" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 6.3 Vulnerability Trend Graph

In Dashboard > **Security Trends**, you can track vulnerability counts over time.

- **Overall trend:** New detections vs. resolved vulnerabilities
- **By severity:** Separate trend lines for Critical / High / Medium / Low
- **Repository comparison:** Side-by-side security score comparison across team repositories

**API example:**
```bash
# Get dashboard statistics
curl -X GET "https://api.vulnix.dev/api/v1/dashboard/stats" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 6.4 Distribution by Severity

The dashboard home page displays a donut chart showing the current distribution of `open` vulnerabilities by severity.

- **Critical:** Immediately exploitable, full service impact
- **High:** High severity, prompt action recommended
- **Medium:** Exploitable under specific conditions
- **Low:** Low risk, recommended for long-term improvement

---

## 7. False Positive Management

### 7.1 Registering Team False Positive Patterns

Vulnix manages false positive patterns at the team level. Vulnerabilities matching registered patterns are automatically filtered out in subsequent scans.

**False positive pattern components:**
- **Semgrep rule ID:** Specifies which Semgrep rule to suppress (e.g., `python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text`)
- **File pattern:** Defines which files the suppression applies to, using a glob pattern (e.g., `tests/**`)
- **Reason:** Documents why this was classified as a false positive

**Registering a pattern from the UI:**
1. Go to Settings > **False Positive Patterns**.
2. Click the **"Add Pattern"** button.
3. Enter the Semgrep rule ID, file pattern, and reason.
4. Click **"Save"**.

**API example:**
```bash
# Register a false positive pattern
curl -X POST "https://api.vulnix.dev/api/v1/false-positives" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "semgrep_rule_id": "python.lang.security.audit.avoid-eval.avoid-eval",
    "file_pattern": "tests/fixtures/**",
    "reason": "Intentional eval usage in test fixture files"
  }'
```

> **Permissions:** Registering or deleting false positive patterns requires the `owner` or `admin` role.

---

### 7.2 Pattern Scope: Using Glob File Patterns

File patterns follow the glob syntax. Use the following rules as a reference.

**Glob pattern examples:**

| Pattern | Scope |
|---|---|
| `tests/**` | All files under the `tests/` directory |
| `**/*.test.ts` | Files ending in `.test.ts` anywhere in the project |
| `src/utils/legacy/**` | All files under `src/utils/legacy/` |
| `**/fixtures/**` | Files under any `fixtures` directory |
| `**` | All files in the entire project |

> **Caution:** Using `**` (all files) as the file pattern will suppress the Semgrep rule across the entire project. It is strongly recommended to specify the narrowest scope possible.

---

### 7.3 Sharing Rules Across the Team

Registered false positive patterns are automatically shared with all team members. New members who join the team will have access to existing patterns immediately.

**Deactivating and restoring patterns:**
```bash
# Deactivate a false positive pattern (soft delete)
curl -X DELETE "https://api.vulnix.dev/api/v1/false-positives/{pattern_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Restore a deactivated pattern
curl -X PUT "https://api.vulnix.dev/api/v1/false-positives/{pattern_id}/restore" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

## 8. Notifications

### 8.1 Connecting Slack Webhooks

Receive vulnerability alerts in a designated Slack channel.

**How to create a Slack Incoming Webhook URL:**
1. Install the **Incoming WebHooks** app from the Slack App Directory.
2. Select the channel where you want to receive notifications.
3. A Webhook URL will be generated (e.g., `https://hooks.slack.com/services/...`).

**Setting it up in Vulnix:**
1. Go to Settings > **Notifications**.
2. Click **"Add Notification Channel"**.
3. Select **Slack** as the platform.
4. Enter the Webhook URL you generated.
5. Set the minimum severity for notifications.
6. Click **"Save"**.

**API example:**
```bash
# Create a Slack notification configuration
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "slack",
    "webhook_url": "https://hooks.slack.com/services/YOUR_WORKSPACE/YOUR_CHANNEL/YOUR_TOKEN",
    "severity_threshold": "high",
    "weekly_report_enabled": true,
    "weekly_report_day": 1
  }'

# Send a test notification
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config/{config_id}/test" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

---

### 8.2 Connecting Microsoft Teams Webhooks

**How to create a Teams Incoming Webhook URL:**
1. Navigate to the channel in Teams where you want to receive notifications.
2. Click **"..."** next to the channel name and select **"Connectors"**.
3. Find **"Incoming Webhook"** and click **"Configure"**.
4. Enter a name for the webhook and click **"Create"**.
5. Copy the generated Webhook URL.

**Setting it up in Vulnix:**
1. In the notification settings, select **Microsoft Teams** as the platform.
2. Enter the Webhook URL and save.

**API example:**
```bash
curl -X POST "https://api.vulnix.dev/api/v1/notifications/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "teams",
    "webhook_url": "https://outlook.office.com/webhook/xxxx",
    "severity_threshold": "critical",
    "weekly_report_enabled": false
  }'
```

---

### 8.3 Setting Up Weekly Security Report Delivery

Vulnix can automatically send a weekly security summary to your notification channel on a specified day.

**Setup steps:**
1. Select the notification channel you want to use.
2. Enable the **"Weekly Report"** toggle.
3. Select the day of the week for delivery (0 = Monday through 6 = Sunday).
4. Click **"Save"**.

**API example:**
```bash
# Enable weekly reports on an existing notification configuration
curl -X PATCH "https://api.vulnix.dev/api/v1/notifications/config/{config_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "weekly_report_enabled": true,
    "weekly_report_day": 1
  }'
```

---

### 8.4 Configuring the Severity Threshold

Control which vulnerability severity levels trigger a notification.

**Severity threshold options:**

| Setting | When notifications are sent |
|---|---|
| `low` | For all vulnerabilities |
| `medium` | For Medium severity and above |
| `high` | For High severity and above |
| `critical` | Only for Critical severity |

---

## 9. CISO Reports

### 9.1 Report Types: CSAP / ISO 27001 / ISMS

Vulnix automatically generates compliance reports aligned with major security certification frameworks.

**Supported report types:**

| Type | Description |
|---|---|
| `csap` | Cloud Security Assurance Program (CSAP) vulnerability status report |
| `iso27001` | ISO/IEC 27001 Information Security Management System evidence report |
| `isms` | Korea Information Security Management System (ISMS) evidence report |

---

### 9.2 Generating a PDF Report

**From the UI:**
1. Click **Reports** in the left sidebar.
2. Click the **"Generate Report"** button.
3. Select the report type (CSAP / ISO 27001 / ISMS).
4. Set the reporting period (start date and end date).
5. Choose the output format (PDF or JSON).
6. Click **"Generate"**.
7. Report generation is handled asynchronously. You will receive a notification when it is ready.
8. Once generation is complete, click the **"Download"** button to retrieve the file.

**API examples:**
```bash
# Request a report (asynchronous)
curl -X POST "https://api.vulnix.dev/api/v1/reports/generate" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "csap",
    "format": "pdf",
    "period_start": "2026-01-01",
    "period_end": "2026-02-28"
  }'

# Example response
{
  "success": true,
  "data": {
    "report_id": "report-uuid",
    "status": "generating",
    "report_type": "csap",
    "estimated_completion_seconds": 30
  }
}

# Check report generation history
curl -X GET "https://api.vulnix.dev/api/v1/reports/history?report_type=csap&status=completed" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# Download a report
curl -X GET "https://api.vulnix.dev/api/v1/reports/{report_id}/download" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -o "report.pdf"
```

---

### 9.3 Setting Up Automatic Report Delivery

Schedule reports to be automatically generated and sent to designated email recipients on a regular basis.

**Setup steps:**
1. Go to Reports > **"Schedule Configuration"** tab.
2. Click **"Add Schedule"**.
3. Select the report type and enter the delivery frequency in cron format.
4. Enter the recipient email addresses.
5. Click **"Save"**.

**Schedule format examples:**
- `@monthly` — Generate on the 1st of every month
- `@weekly` — Generate every Monday
- `0 9 1 * *` — Generate at 9:00 AM on the 1st of every month

**API example:**
```bash
# Create an automated report delivery schedule
curl -X POST "https://api.vulnix.dev/api/v1/reports/config" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "isms",
    "schedule": "@monthly",
    "email_recipients": ["ciso@company.com", "security@company.com"],
    "is_active": true
  }'
```

---

## 10. VS Code Extension

### 10.1 Installation

**Installing from the VS Code Marketplace:**
1. Open VS Code.
2. Click the **Extensions** icon in the left sidebar.
3. Search for `Vulnix Security Scanner`.
4. Click on **"Vulnix Security Scanner"** in the results and click **"Install"**.

**Installing from a VSIX file (offline):**
1. Download the VSIX file from the Vulnix dashboard under Settings.
2. In VS Code, open the Command Palette with `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`).
3. Run `Extensions: Install from VSIX...`.
4. Select the downloaded VSIX file.

---

### 10.2 Generating an API Key

The VS Code extension requires an API key to communicate with the Vulnix server.

**How to generate an API key:**
1. In the Vulnix dashboard, go to Settings > **API Keys**.
2. Click **"Generate New API Key"**.
3. Enter a name for the key (e.g., "VS Code - Personal Laptop").
4. Optionally, set an expiration date.
5. Click **"Generate"**.
6. Copy the generated API key (`vx_live_...` format). **This value cannot be viewed again after you leave the page.**

> **Permissions:** Only users with the `owner` or `admin` role can generate API keys.

---

### 10.3 Configuring the Extension (serverUrl, apiKey)

**Via the VS Code Settings UI:**
1. Open Settings with `Ctrl+,` (Mac: `Cmd+,`).
2. Search for `vulnix`.
3. Fill in the following settings.

| Setting | Key | Default | Description |
|---|---|---|---|
| Server URL | `vulnix.serverUrl` | `https://api.vulnix.dev` | Vulnix API server address |
| API Key | `vulnix.apiKey` | (empty) | Your generated API key |
| Analyze on Save | `vulnix.analyzeOnSave` | `true` | Automatically analyze when saving a file |
| Severity Filter | `vulnix.severityFilter` | `all` | Minimum severity to display (`all` / `high` / `critical`) |

**Configuring via settings.json:**
```json
{
  "vulnix.serverUrl": "https://api.vulnix.dev",
  "vulnix.apiKey": "vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "vulnix.analyzeOnSave": true,
  "vulnix.severityFilter": "all"
}
```

---

### 10.4 Using Real-Time Vulnerability Highlighting

Once configured, the extension automatically analyzes Python, JavaScript, TypeScript, Java, and Go files when you save them.

**How highlighting works:**
- A red squiggly underline appears beneath code lines where vulnerabilities are detected.
- Hover over the underline to see a popup with the vulnerability description.
- Warning icons appear in the left editor gutter.
- The VS Code **Problems** panel (`Ctrl+Shift+M`) shows a complete list of vulnerabilities in the current file.

**Highlight colors by severity:**
- Critical / High: Red underline
- Medium: Orange underline
- Low: Yellow underline

---

### 10.5 Applying Patches Automatically

You can apply an AI-generated patch directly from the vulnerable code line.

**Steps to apply a patch:**
1. Click on a code line with a red squiggly underline.
2. Click the **light bulb icon (Quick Fix)** that appears to the left of the line.
3. Select **"Vulnix: Apply Patch Fix"**.
4. A "Generating patch suggestion..." progress indicator will appear.
5. Once complete, the code will be automatically updated and a success message will be shown.

> **Caution:** Save your current work and consider making a git commit before applying a patch. Always review the patched code afterward.

---

### 10.6 Command Palette Reference

Press `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`) to open the Command Palette and run the following Vulnix commands.

| Command | Description |
|---|---|
| `Vulnix: Analyze Current File` | Immediately analyze the currently open file |
| `Vulnix: Apply Patch Fix` | Apply a patch to the selected vulnerability |
| `Vulnix: Show Vulnerability Detail` | Open a webview with full vulnerability details |
| `Vulnix: Sync False Positive Patterns` | Sync the latest false positive patterns from the server |
| `Vulnix: Clear All Diagnostics` | Remove all current vulnerability highlights |

---

## 11. API Key Management

### 11.1 Generating IDE API Keys

API keys are used by IDE tools such as the VS Code extension to authenticate with the Vulnix server. They are managed separately from JWT tokens.

**Generation steps:**
1. In the Vulnix dashboard, go to Settings > **API Keys**.
2. Click **"Generate New API Key"**.
3. Enter a descriptive name (choose a name that clearly identifies its purpose).
4. Set an expiration period (30 days, 90 days, 1 year, or no expiration).
5. Click **"Generate"**.
6. Copy the full API key value to a secure location. **It will not be displayed again.**

**API example:**
```bash
# Generate an API key
curl -X POST "https://api.vulnix.dev/api/v1/ide/api-keys" \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VS Code - Development Laptop",
    "expires_in_days": 365
  }'

# Example response
{
  "success": true,
  "data": {
    "id": "key-uuid",
    "name": "VS Code - Development Laptop",
    "key": "vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "key_prefix": "vx_live_xxxx",
    "expires_at": "2027-02-26T00:00:00Z",
    "created_at": "2026-02-26T00:00:00Z"
  }
}
```

---

### 11.2 Deactivating an API Key

Deactivate any API key that is no longer in use. Requests made with a deactivated key will be rejected immediately.

**From the UI:**
1. Go to Settings > API Keys and locate the key you want to deactivate.
2. Click the **"Deactivate"** button next to that key.
3. Confirm the action in the dialog.

**API example:**
```bash
# Deactivate an API key
curl -X DELETE "https://api.vulnix.dev/api/v1/ide/api-keys/{key_id}" \
  -H "Authorization: Bearer {JWT_TOKEN}"

# List all API keys
curl -X GET "https://api.vulnix.dev/api/v1/ide/api-keys" \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

> **Security recommendation:** If an API key is compromised, deactivate it immediately and generate a new one.

---

## 12. Troubleshooting

### 12.1 Scan Does Not Start

**Symptom:** You pushed code to a repository, but an automatic scan did not begin.

**Things to check:**

1. **Verify webhook registration**
   - GitHub: Go to the repository Settings > Webhooks and confirm the Vulnix webhook is listed.
   - Webhook URL: `https://api.vulnix.dev/api/v1/webhooks/github`
   - Check the recent delivery history to see if responses are returning a 200 status code.

2. **Check repository active status**
   - Confirm the repository has `is_active: true` in the Vulnix dashboard.

3. **Run a manual scan as a workaround**
   ```bash
   curl -X POST "https://api.vulnix.dev/api/v1/scans" \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"repo_id": "{repo_id}", "branch": "main"}'
   ```

4. **Check for an in-progress scan**
   - A new scan will not start if a scan is already queued or running for the same repository.
   - Check Dashboard > Scan History for any scans with `queued` or `running` status.

---

### 12.2 Webhooks Are Not Being Received

**Symptom:** Events occurred on GitHub/GitLab/Bitbucket, but Vulnix did not receive them.

**Things to check:**

1. **Verify the webhook secret matches**
   - GitHub: Go to repository Settings > Webhooks > Edit the webhook and confirm the secret matches what is configured in Vulnix.

2. **Verify the webhook event types are selected**
   - GitHub webhooks must have `push` and `pull_request` events checked.
   - GitLab webhooks must have `Push events` and `Merge request events` enabled.

3. **Check network accessibility**
   - Verify that the Vulnix server is reachable from the internet.
   - For local development environments, use a tunneling tool such as ngrok.

4. **Review the webhook delivery log**
   - GitHub: Go to repository Settings > Webhooks > recent deliveries and check the response codes.
   - If the response code is 4xx or 5xx, check the server logs.

---

### 12.3 Patch PRs Are Not Being Created

**Symptom:** A vulnerability was detected, but a patch PR was not automatically generated.

**Things to check:**

1. **Check GitHub App permissions**
   - Confirm the GitHub App has `pull_requests: write` and `contents: write` permissions.

2. **Check vulnerability severity**
   - Patch PRs are generated by default only for vulnerabilities of `medium` severity and above.

3. **Check branch protection rules**
   - Branch protection rules that block direct pushes to the default branch may cause PR creation to fail.
   - Vulnix creates a patch branch and submits a PR from it, so it requires permission to create branches.

4. **Manually request a patch**
   - Click the **"Regenerate Patch"** button on the vulnerability detail page.

---

### 12.4 VS Code Extension Connection Error

**Symptom:** VS Code shows "API key is not configured" or "Cannot connect to server".

**Resolution steps:**

1. **Verify the API key setting**
   - Confirm that `vulnix.apiKey` is correctly entered in VS Code settings.
   - Expected format: `vx_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

2. **Verify the server URL**
   - Confirm that `vulnix.serverUrl` is correct. Default: `https://api.vulnix.dev`
   - If running a self-hosted deployment, update this to your internal URL.

3. **Test the API key directly**
   ```bash
   # Test the API key with a code analysis request
   curl -X POST "https://api.vulnix.dev/api/v1/ide/analyze" \
     -H "X-Api-Key: vx_live_xxxx" \
     -H "Content-Type: application/json" \
     -d '{
       "content": "import os\nos.system(input())",
       "language": "python",
       "file_path": "test.py"
     }'
   ```

4. **Check whether the API key is deactivated**
   - In the Vulnix dashboard, go to Settings > API Keys and confirm the key is active.
   - If the key has expired, generate a new one.

5. **Restart VS Code**
   - Fully close and reopen VS Code after making configuration changes.
   - Run `Vulnix: Sync False Positive Patterns` from the Command Palette to test the connection.

---

## Further Assistance

- **Official documentation:** `https://docs.vulnix.dev`
- **Technical support:** `support@vulnix.dev`
- **GitHub Issues:** `https://github.com/vulnix/vulnix/issues`

---

*Vulnix User Manual v1.0 | February 2026*
