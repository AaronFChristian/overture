variable "project_name" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "overture"
}

variable "environment" {
  description = "Environment tag/suffix. Kept as 'dev' -- this project has no staging/prod split."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region. Must be one of this subscription's allowed deployment regions -- Azure for Students subscriptions commonly restrict this via policy. Confirmed allowed for this subscription: westus3, mexicocentral, canadacentral, centralus, eastus (westus2 is NOT allowed, despite being a reasonable-looking default -- discovered via a real failed apply, not guessed in advance). westus3 chosen as the closest allowed region to San Diego."
  type        = string
  default     = "westus3"
}

variable "my_ip_address" {
  description = <<-EOT
    Your current public IP address, so Postgres's firewall allows you
    to connect and run `alembic upgrade head` from your laptop.
    Find it with: curl -s ifconfig.me
    This WILL change if you're on a different network later --
    re-run `terraform apply` after updating this value if `alembic`
    or `overture extract` can't reach the database.
  EOT
  type        = string
}

variable "alert_email" {
  description = "Email address for budget alert notifications."
  type        = string
}

variable "postgres_sku_name" {
  description = "Postgres Flexible Server SKU. B_Standard_B1ms is the cheapest burstable tier -- see decisions.md D-0007 (original stack decision) and the cost math from early planning."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  description = "Minimum allowed storage for Postgres Flexible Server."
  type        = number
  default     = 32768
}

variable "budget_amount_usd" {
  description = "Monthly budget alert threshold in USD. Matches the $25 per-project cap discussed during cost planning -- well under the $100 total credit, leaving room for the other two portfolio projects."
  type        = number
  default     = 25
}

variable "github_repo" {
  description = "GitHub repo in 'owner/name' form, used to scope the OIDC federated credential so ONLY workflow runs from this exact repo (on the main branch) can obtain an Azure token. See decisions.md D-0031."
  type        = string
  default     = "AaronFChristian/overture"
}

variable "enable_github_actions_oidc" {
  description = <<-EOT
    Whether to create the Entra ID app registration for GitHub Actions
    OIDC deploy. Defaults to false: SDSU's Entra ID tenant blocks
    student accounts from registering applications (confirmed via a
    direct `az ad app create` test, not assumed -- see decisions.md
    D-0036). The OIDC design and code are kept intact and correct for
    a tenant that permits app registration; this flag lets the rest
    of the landing zone deploy without repeatedly hitting that wall.
  EOT
  type        = bool
  default     = false
}
