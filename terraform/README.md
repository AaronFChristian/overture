# Overture — Azure landing zone

Provisions the empty infrastructure Overture will deploy into in
session 8: resource group, Postgres Flexible Server (pgvector-enabled),
Container Apps environment, Key Vault, managed identity, Application
Insights, and a budget alert. Does **not** deploy the app itself.

## First-time setup

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
- `my_ip_address` — get yours with `curl -s ifconfig.me`
- `alert_email` — where budget threshold emails go

`terraform.tfvars` is gitignored. Never commit it.

## The sequence, every time

```bash
terraform init       # downloads the azurerm provider plugin, once
terraform validate   # checks syntax and internal consistency, zero cost
terraform fmt -check # confirms formatting, zero cost
terraform plan        # shows exactly what WOULD be created, zero cost
```

Read the plan output before doing anything else. It should show
resources being **created**, never destroyed or replaced, on a first
run.

```bash
terraform apply       # THIS IS WHERE REAL SPEND BEGINS
```

Terraform will show the same plan again and ask you to type `yes`.
That's the actual confirmation point.

## After apply

Two things Terraform deliberately does NOT do for you:

**Add your real API keys to Key Vault.** Terraform only manages
secrets it generated itself (the Postgres password) — see
decisions.md D-0026. Add your Anthropic key manually:

```bash
az keyvault secret set \
  --vault-name "$(terraform output -raw key_vault_name)" \
  --name anthropic-api-key \
  --value "sk-ant-your-real-key"
```

**Verify the pgvector extension is actually usable.** The Terraform
config allow-lists it at the server level, but `CREATE EXTENSION
vector` still happens per-database — that's what Alembic migration
`0002_add_chunks.py` already does. You'd run that against this cloud
database in session 8, not this session.

## Deploying the app (session 8+)

After `terraform apply`, one-time setup in the GitHub repo (Settings →
Secrets and variables → Actions → Variables tab) -- these are
**variables**, not secrets, since OIDC needs no secret at all:

```bash
terraform output github_actions_client_id
terraform output azure_tenant_id
terraform output azure_subscription_id
terraform output resource_group_name
terraform output container_app_name
```

Set each as a repository variable: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `CONTAINER_APP_NAME`.

**Also make the GHCR package public** after the first deploy run
creates it (repo → Packages → overture → Package settings → Change
visibility). See decisions.md D-0033 for why this is a deliberate,
low-risk choice rather than an oversight -- no secrets are ever baked
into the image itself.

Then trigger the deploy from GitHub's Actions tab: **Deploy to Azure
Container Apps → Run workflow**. It's manual on purpose (D-0033) --
this project's infrastructure doesn't exist between sessions, so an
auto-deploy-on-push would fail on any unrelated push.

## Tearing down

```bash
terraform destroy
```

Then verify nothing survived:

```bash
az resource list --resource-group "$(terraform output -raw resource_group_name)" --output table
```

Empty output means clean. Anything listed means something didn't
destroy — investigate before walking away.

Or use the wrapper scripts from the repo root, which do both of the
above for you:

```bash
../scripts/demo-up.sh     # init, validate implicitly via plan, plan
../scripts/demo-down.sh   # destroy + emptiness check
```

## What this costs

See decisions.md D-0028 for the reasoning: a $25/month budget alert
(50/80/100% thresholds) is configured, well under the $100 total
credit. Actual spend for a build → verify → record → destroy cycle
should land in the low single digits — see the cost math from early
project planning (decisions.md, pre-session-1 discussion).
