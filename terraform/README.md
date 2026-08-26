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
