# Vault names must be globally unique across all of Azure -- appending
# a short random suffix avoids a naming collision with someone else's
# "kv-overture-dev" somewhere else in the world.
resource "random_string" "kv_suffix" {
  length  = 4
  special = false
  upper   = false
}

resource "azurerm_key_vault" "main" {
  name                = "kv-${var.project_name}-${random_string.kv_suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Purge protection stays OFF -- see providers.tf's
  # purge_soft_delete_on_destroy setting. A demo environment destroyed
  # at the end of every session cannot afford a vault stuck in
  # Azure's mandatory 90-day soft-delete retention; that would block
  # ever reusing this exact vault name again without manually purging
  # it out of band.
  purge_protection_enabled = false

  tags = local.common_tags
}

# Aaron's own `az login` identity -- lets him inspect/rotate secrets
# manually via `az keyvault secret show`, matching how every prior
# session has been verified directly from his terminal.
resource "azurerm_key_vault_access_policy" "operator" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

# The app's managed identity -- read-only, and only what the running
# app actually needs at runtime, not the broader permissions Aaron's
# own operator access has.
resource "azurerm_key_vault_access_policy" "app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.app.principal_id

  secret_permissions = ["Get", "List"]
}

# --- Secrets Terraform is allowed to manage ------------------------------
# ONLY secrets Terraform itself generated go here (D-0026). The
# Anthropic API key, and Azure OpenAI credentials if ever used, are
# NOT defined as Terraform resources anywhere in this configuration --
# they already exist, Aaron already owns them, and putting them in a
# .tf file or a tfvars file would risk them landing in git history or
# Terraform state in plaintext for no benefit. They're added directly
# via `az keyvault secret set` after `apply` finishes -- see the
# README this file ships alongside.

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  key_vault_id = azurerm_key_vault.main.id
  value        = "postgresql+asyncpg://${azurerm_postgresql_flexible_server.main.administrator_login}:${urlencode(random_password.postgres_admin.result)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.overture.name}"

  depends_on = [azurerm_key_vault_access_policy.operator]
}

# Real, generated share-token secret for the deployed app -- replaces
# the "local-dev-only-placeholder" default from config.py. Same
# reasoning as the Postgres password (D-0026): Terraform generates
# it, so Terraform is allowed to manage it as a secret.
resource "random_password" "share_token_secret" {
  length  = 48
  special = false # itsdangerous's serializer doesn't need special chars, plain alphanumeric is simplest
}

resource "azurerm_key_vault_secret" "share_token_secret" {
  name         = "share-token-secret"
  key_vault_id = azurerm_key_vault.main.id
  value        = random_password.share_token_secret.result

  depends_on = [azurerm_key_vault_access_policy.operator]
}
