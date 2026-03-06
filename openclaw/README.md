# Talent Scout — OpenClaw Skills

AI-powered job search automation as 8 composable OpenClaw skills. This is a **private installation** — not published to Clawhub. Install directly from the repo onto your OpenClaw instance running on an Ubuntu VM.

**Two accounts are involved throughout this guide:**

| Account | Role | Actions |
|---------|------|---------|
| `ronrlin` | Repository owner | Reviews and merges PRs |
| *(agent account)* | OpenClaw bot | Forks the repo, pushes branches, opens PRs against `ronrlin/talent-scout` |

The `ronrlin/talent-scout` repository is **public**. No collaborator invitation is needed — the agent contributes through the standard fork-and-PR workflow.

---

## Prerequisites

- An Ubuntu VM (Hostinger VPS or similar) with SSH access
- A running [OpenClaw](https://openclaw.dev) instance on the VM
- An Anthropic API key (`ANTHROPIC_API_KEY`)

---

## 1. Setting Up GitHub for Your OpenClaw Agent

These steps are done **in a browser** (on your local machine, not on the VM). They create the agent's GitHub identity, fork the repo, and generate an access token.

### 1a. Create a GitHub account for the agent

The agent needs its own GitHub identity, separate from `ronrlin`. Create a dedicated machine user account at [github.com/signup](https://github.com/signup):

| Field | Suggested value |
|-------|-----------------|
| Username | Something identifiable as a bot, e.g. `ronrlin-openclaw-bot` |
| Email | A real address you control. A Gmail `+` alias like `ronrlin+openclaw@gmail.com` keeps it separate from your personal account. |
| Password | Strong and unique. Store it in a password manager. |

After account creation:

1. **Verify the email** — GitHub requires this before the account can fork repos or open PRs.
2. **Set the profile** at [github.com/settings/profile](https://github.com/settings/profile):
   - Name: `OpenClaw Agent` (this is the name that appears on PRs and commits)
   - Bio: `Automated agent for ronrlin/talent-scout`
3. **Note the noreply email** at [github.com/settings/emails](https://github.com/settings/emails). It looks like:
   ```
   12345678+ronrlin-openclaw-bot@users.noreply.github.com
   ```
   You'll use this for git commits on the VM so the agent's real email stays private.

> GitHub's Terms of Service allow machine/bot accounts as long as a human (you) is responsible for the account's actions.

### 1b. Fork the repository

While logged in as the agent account (not `ronrlin`), go to [github.com/ronrlin/talent-scout](https://github.com/ronrlin/talent-scout) and click **Fork**. This creates `<agent-username>/talent-scout` under the agent's account.

### 1c. Create a fine-grained Personal Access Token

Still logged in as the agent account, go to [Settings > Developer settings > Fine-grained tokens](https://github.com/settings/personal-access-tokens/new) and create a token scoped to the agent's fork:

| Setting | Value |
|---------|-------|
| Token name | `openclaw-vm` |
| Expiration | 90 days (or your preference) |
| Resource owner | *(the agent's own account)* |
| Repository access | **Only select repositories** > `<agent-username>/talent-scout` |
| Permissions — Contents | **Read and write** (push branches to fork) |
| Permissions — Pull requests | **Read and write** (open PRs against upstream) |
| Permissions — Metadata | **Read-only** (auto-selected) |

No other permissions are needed. Copy the token — it starts with `github_pat_`.

> **Token rotation:** Fine-grained PATs expire. Set a calendar reminder. When you rotate, update `.env` on the VM and re-run `gh auth login --with-token` (see section 3 below).

---

## 2. Installing on Ubuntu

### Approach A: Direct Install (Recommended)

Clone the repo, install into a venv, register skills. Best for iterating — just `git pull` and restart.

**Step 1 — System packages**

```bash
sudo apt-get update && sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  git build-essential pkg-config \
  libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
  libcairo2 libcairo2-dev \
  libgdk-pixbuf2.0-0 \
  libglib2.0-0 libglib2.0-dev \
  libffi-dev \
  fonts-liberation fonts-dejavu-core
```

> If your Ubuntu ships Python 3.12+ and not 3.11, replace `python3.11` with `python3` throughout. Any >= 3.11 works. On Ubuntu 22.04 you may need the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa):
> ```bash
> sudo add-apt-repository ppa:deadsnakes/ppa
> sudo apt-get update && sudo apt-get install python3.11 python3.11-venv python3.11-dev
> ```

**Step 2 — Clone and create venv**

```bash
cd /opt
sudo git clone https://github.com/ronrlin/talent-scout.git
sudo chown -R $USER:$USER /opt/talent-scout
cd /opt/talent-scout

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e "."
```

For Firecrawl fallback scraping (optional):

```bash
pip install -e ".[firecrawl]"
```

**Step 3 — Install scout-tools**

`scout-tools` is the CLI bridge between OpenClaw skills and the talent-scout data layer.

```bash
pip install -e openclaw/shared/scripts/
scout-tools --help   # verify
```

**Step 4 — Environment variables**

```bash
cat > /opt/talent-scout/.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
GH_TOKEN=github_pat_...           # PAT from section 1c
FIRECRAWL_API_KEY=fc-...          # Optional — for JS-heavy job sites
TALENT_SCOUT_API_KEY=             # Auto-generated on first API start if blank
EOF

# Source it (add to ~/.bashrc for persistence)
set -a; source /opt/talent-scout/.env; set +a
```

**Step 5 — Bootstrap the workspace**

```bash
cd /opt/talent-scout

# Create required directories
mkdir -p data/research input output/{resumes,cover-letters,analysis,interview-prep}

# Add your base resume
cp /path/to/your/resume.md input/base-resume.md

# Create config.json (edit preferences after)
cat > config.json << 'CONF'
{
  "user": {
    "name": "Your Name",
    "email": "you@example.com",
    "linkedin_url": "https://linkedin.com/in/you",
    "base_resume_path": "./input/base-resume.md"
  },
  "preferences": {
    "locations": ["Palo Alto, CA"],
    "include_remote": true,
    "roles": ["Software Engineer"],
    "min_company_size": 100,
    "prefer_public_companies": true,
    "companies_per_location": 15,
    "output_format": "pdf",
    "pipeline": {
      "follow_up_days": 7,
      "follow_up_reminder_days": [7, 14],
      "auto_ghost_days": 30
    }
  },
  "seeds": {
    "include": "./input/target-companies.json",
    "exclude": "./input/excluded-companies.json"
  }
}
CONF
```

**Step 6 — Register skills with OpenClaw**

```bash
for skill in scout-setup scout-companies scout-research scout-analyze \
             scout-resume scout-cover-letter scout-interview-prep scout-pipeline; do
  openclaw skills register /opt/talent-scout/openclaw/skills/$skill
done
```

> Adjust `openclaw skills register` to match your OpenClaw version's CLI. If your instance uses a config file for skill registration, add the paths there instead.

**Step 7 — Verify**

```bash
source .venv/bin/activate
python -c "import anthropic; print('SDK OK')"
scout-tools data classify-location "Palo Alto, CA"
python scout.py --help
```

**Step 8 — (Optional) Start the REST API**

```bash
source .venv/bin/activate
cd /opt/talent-scout
python scout.py serve --host 0.0.0.0 --port 8000
```

Or with uvicorn directly:

```bash
uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000
```

---

### Approach B: Docker

Runs the REST API in a container. Useful for isolation from the host Python.

**Step 1 — Install Docker**

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Log out and back in for group change
```

**Step 2 — Clone and configure**

```bash
cd /opt
sudo git clone https://github.com/ronrlin/talent-scout.git
sudo chown -R $USER:$USER /opt/talent-scout
cd /opt/talent-scout

mkdir -p data/research input output/{resumes,cover-letters,analysis,interview-prep}
# Add resume, config.json, and .env (same as Approach A steps 4-5)
```

**Step 3 — Build and run**

```bash
cd /opt/talent-scout
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build -d
```

The `docker-compose.yml` mounts `config.json`, `input/`, `data/`, and `output/` as volumes so data persists on the host.

**Step 4 — Install scout-tools on the host**

The OpenClaw skills invoke `scout-tools` on the host, not inside the container. Even with Docker running the API, you need a native install for skill execution:

```bash
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
  libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 \
  libglib2.0-0 libffi-dev fonts-liberation

python3.11 -m venv /opt/talent-scout/.venv
source /opt/talent-scout/.venv/bin/activate
pip install -e /opt/talent-scout
pip install -e /opt/talent-scout/openclaw/shared/scripts/
```

Then register skills (same as Approach A step 6).

> **Docker limitation:** Docker only runs the REST API. OpenClaw skills still need host-level `scout-tools` and the project Python packages.

**Step 5 — Verify API**

```bash
cat /opt/talent-scout/data/.api-key

curl -s -H "X-API-Key: $(cat /opt/talent-scout/data/.api-key)" \
  http://localhost:8000/api/v1/pipeline | python3 -m json.tool
```

---

### Approach C: systemd Service

After completing Approach A, add a systemd unit so the API starts on boot and restarts on failure.

```bash
sudo tee /etc/systemd/system/talent-scout.service << 'EOF'
[Unit]
Description=Talent Scout API
After=network.target

[Service]
Type=simple
User=ron
WorkingDirectory=/opt/talent-scout
EnvironmentFile=/opt/talent-scout/.env
ExecStart=/opt/talent-scout/.venv/bin/uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable talent-scout
sudo systemctl start talent-scout

# Check status
sudo systemctl status talent-scout
journalctl -u talent-scout -f
```

---

## 3. Setting Up GitHub on the VM

These steps are done **on the VM** (via SSH). They configure git and the `gh` CLI so the OpenClaw agent can push branches to its fork and open PRs against `ronrlin/talent-scout`.

**Prerequisite:** You must have completed section 1 (the agent has a GitHub account, a fork, and a PAT) and section 2 (the repo is cloned to `/opt/talent-scout`).

### 3a. Install the `gh` CLI

```bash
sudo apt-get update && sudo apt-get install -y gh
```

If `gh` is not in the default Ubuntu repos:

```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt-get update && sudo apt-get install -y gh
```

### 3b. Authenticate as the agent account

Use the PAT from section 1c:

```bash
echo "$GH_TOKEN" | gh auth login \
  --with-token \
  --hostname github.com \
  --git-protocol https
```

If you already sourced `.env` (from section 2, step 4), `$GH_TOKEN` is available. Otherwise substitute the token directly.

This does two things:
- Configures `gh` for API calls (creating PRs from the fork against `ronrlin/talent-scout`)
- Sets up the git credential helper so `git push` to the fork works over HTTPS without prompting

### 3c. Configure git identity

Set the agent's name and noreply email (from section 1a) so commits are attributed to the agent's GitHub account. These are scoped to this repo only:

```bash
cd /opt/talent-scout
git config user.name "OpenClaw Agent"
git config user.email "12345678+ronrlin-openclaw-bot@users.noreply.github.com"
```

Replace the email with the actual noreply address from section 1a.

### 3d. Configure git remotes

Set up two remotes — `origin` for pulling upstream changes, `fork` for pushing the agent's branches:

```bash
cd /opt/talent-scout

# 'origin' points to the upstream repo (read-only for the agent)
git remote set-url origin https://github.com/ronrlin/talent-scout.git

# 'fork' points to the agent's fork (push target)
git remote add fork https://github.com/<agent-username>/talent-scout.git
```

### 3e. Verify

```bash
# Check gh authentication
gh auth status
# => Logged in to github.com as <agent-username>

# Check git identity
git config user.name
# => OpenClaw Agent

# Check remotes
git remote -v
# origin  https://github.com/ronrlin/talent-scout.git (fetch)
# origin  https://github.com/ronrlin/talent-scout.git (push)
# fork    https://github.com/<agent-username>/talent-scout.git (fetch)
# fork    https://github.com/<agent-username>/talent-scout.git (push)

# Test connectivity
git fetch origin
git fetch fork
```

### Agent PR workflow

Once everything is configured, the agent's workflow for suggesting improvements is:

```bash
git pull origin main                # Pull latest from ronrlin/talent-scout
git checkout -b improvement/foo     # Create a feature branch
# ... make changes ...
git push fork improvement/foo       # Push to the agent's fork

gh pr create \
  --repo ronrlin/talent-scout \
  --head <agent-username>:improvement/foo \
  --base main \
  --title "Improvement: foo" \
  --body "Description of changes"
```

The PR appears on `ronrlin/talent-scout` for review. The repo owner (`ronrlin`) merges it.

> **Alternative — SSH for git operations:** Generate a keypair on the VM (`ssh-keygen -t ed25519`), add the public key to the agent's GitHub account at [github.com/settings/keys](https://github.com/settings/keys), and update the fork remote: `git remote set-url fork git@github.com:<agent-username>/talent-scout.git`. The `origin` remote can stay HTTPS since the repo is public. The PAT is still needed for `gh pr create`.

---

## First-Run Setup

After completing sections 1-3:

1. Run `/scout-setup` in your OpenClaw instance to parse your resume and verify config
2. Edit `config.json` with your real locations, roles, and preferences
3. Optionally add seed companies at `input/target-companies.json`:
   ```json
   [{"name": "Company Name", "reason": "Why you're interested"}]
   ```

---

## Workflow

```
scout-companies > scout-research > scout-analyze > scout-resume > scout-cover-letter
         |____________________ scout-pipeline (track everything) ____________________|
```

### Scout companies

Find companies hiring in your target locations:

```
/scout-companies Palo Alto, CA
```

### Research a company

Deep-dive on a company — find open jobs, culture, leadership:

```
/scout-research Stripe
```

Or import a specific job from a URL:

```
/scout-research https://careers.stripe.com/listing/senior-engineer
```

### Analyze a job

Get match scores, gap analysis, and resume strategy:

```
/scout-analyze JOB-STRIPE-a1b2c3
```

### Generate a resume

Create a tailored resume for the job:

```
/scout-resume JOB-STRIPE-a1b2c3
```

To improve an existing resume with surgical edits:

```
/scout-resume JOB-STRIPE-a1b2c3 --improve
```

### Generate a cover letter

```
/scout-cover-letter JOB-STRIPE-a1b2c3
```

### Prepare for interviews

```
/scout-interview-prep JOB-STRIPE-a1b2c3
```

### Track your pipeline

See what needs attention next:

```
/scout-pipeline next
```

Record an application:

```
/scout-pipeline apply JOB-STRIPE-a1b2c3
```

View pipeline overview:

```
/scout-pipeline pipeline
```

---

## Skills Reference

| Skill | Description | Key Features |
|-------|-------------|-------------|
| `scout-setup` | Initialize workspace | Config creation, resume parsing, profile management |
| `scout-companies` | Find target companies | Location-aware, scoring, seed/exclusion lists |
| `scout-research` | Research companies + import jobs | Company name, URL, or pasted text input |
| `scout-analyze` | Analyze job fit | Match scoring, gap analysis, role archetypes |
| `scout-resume` | Generate/improve resumes | Two-pass generation, three-phase improvement |
| `scout-cover-letter` | Generate cover letters | Two-pass with anti-pattern enforcement |
| `scout-interview-prep` | Interview preparation | Talking points, STAR stories, questions to ask |
| `scout-pipeline` | Pipeline management | Action dashboard, status tracking, learning |

---

## Data Files

All data is stored locally in the project directory:

```
config.json                     # Search preferences and configuration
data/
  candidate-profile.json        # Parsed resume profile
  pipeline.json                 # Application pipeline state
  jobs-<location-slug>.json     # Jobs by location
  companies-<location-slug>.json # Scouted companies by location
  research/<company-slug>.json  # Company research
  learned-preferences.json      # Patterns learned from your feedback
input/
  base-resume.md                # Your source resume
output/
  resumes/                      # Generated resumes
  cover-letters/                # Generated cover letters
  analysis/                     # Job analyses
  interview-prep/               # Interview prep docs
```

---

## Troubleshooting

**`scout-tools` not found:**
```bash
source /opt/talent-scout/.venv/bin/activate
pip install -e /opt/talent-scout/openclaw/shared/scripts/
```

**PDF generation fails on Ubuntu:**
Install the WeasyPrint system libraries:
```bash
sudo apt-get install -y \
  libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
  libcairo2 libgdk-pixbuf2.0-0 libglib2.0-0 libffi-dev \
  fonts-liberation fonts-dejavu-core
```
Note: `DYLD_LIBRARY_PATH` is macOS-only and is **not needed** on Linux.

**"No profile found" errors:**
Run `/scout-setup` first — or `/scout-setup refresh-profile` if your base resume changed.

**Location classification questions:**
```bash
scout-tools data classify-location "San Francisco, CA"
```

**API not starting:**
```bash
journalctl -u talent-scout --no-pager -n 50

# Or run interactively to see errors
cd /opt/talent-scout && source .venv/bin/activate
python scout.py serve --port 8000
```

**Firecrawl fallback not working:**
```bash
pip show firecrawl-py          # Verify installation
echo $FIRECRAWL_API_KEY        # Verify API key
tail -20 /opt/talent-scout/error.log  # Check escalation details
```

**`gh` auth expired or failing:**
```bash
gh auth status                 # Check current state
# Re-authenticate with a new token:
echo "github_pat_NEW_TOKEN" | gh auth login --with-token --hostname github.com --git-protocol https
# Update .env:
sed -i 's/^GH_TOKEN=.*/GH_TOKEN=github_pat_NEW_TOKEN/' /opt/talent-scout/.env
```

---

## TODOs

Changes to make in talent-scout to improve the Ubuntu / remote-server experience:

- [ ] **Make WeasyPrint an optional dependency.** It is currently in the main `dependencies` list in `pyproject.toml`, which means `pip install .` fails if the system libraries (Pango, Cairo) are missing. Move it to an optional group like `[pdf]` so the base install always succeeds, and PDF generation gracefully degrades to markdown-only. `document_converter.py` already catches the ImportError — only `pyproject.toml` needs to change.

- [ ] **Make `scout-tools` importable without the full project installed.** `scout_tools.py` imports `config_loader`, `data_store`, `pipeline_store`, and `document_converter` from the main project. This means installing `talent-scout-scripts` alone (as the clawhub manifests specify) will fail — you must install the entire `talent-scout` package. Either vendor the needed modules into the scripts package, or declare `talent-scout` as a dependency of `talent-scout-scripts`.

- [ ] **Add a `clawhub.yaml` install step for apt packages on Linux.** The current manifests use `kind: brew` for WeasyPrint, which only works on macOS. Add a parallel `kind: apt` step (or shell step) so `openclaw skills install` can set up system libraries on Ubuntu automatically.

- [ ] **Pin the `DYLD_LIBRARY_PATH` advice to macOS only.** The main project `README.md` mentions this env var without qualifying that it is macOS-specific. On Linux, the system libraries are found via `ld.so` and no library path override is needed. Guard or annotate.

- [ ] **Add a health-check endpoint or CLI command.** Something like `scout health` or `GET /api/v1/health` that verifies: Python version OK, Anthropic SDK importable, API key set, WeasyPrint available (or not), data directories exist. Useful for validating a fresh install on a remote server.

- [ ] **Support configurable data/output paths.** Paths are currently relative to the working directory. On a server, it's easy to run the CLI or API from the wrong directory and get empty results or write data to unexpected locations. Consider honoring a `TALENT_SCOUT_HOME` env var or an absolute-path config option.

- [ ] **`clawhub.yaml` `install.kind: brew` won't work on Ubuntu.** The `weasyprint` install step in every skill manifest uses `kind: brew`. On Ubuntu, this step will silently fail or error. Provide a `kind: apt` alternative or a `kind: shell` fallback with the `apt-get install` command.
