output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgres_database_name" {
  value = azurerm_postgresql_flexible_server_database.overture.name
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.main.id
}

output "app_managed_identity_client_id" {
  value = azurerm_user_assigned_identity.app.client_id
}

output "application_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}

output "database_url_secret_name" {
  description = "Secret name in Key Vault -- the DB URL itself is never printed to the terminal."
  value       = azurerm_key_vault_secret.database_url.name
}

# --- Values needed as GitHub Actions repository VARIABLES (not
# secrets -- none of these are sensitive; OIDC needs no client secret
# at all, see oidc.tf) -----------------------------------------------

output "github_actions_client_id" {
  description = "Set as the AZURE_CLIENT_ID repository variable in GitHub. Null when enable_github_actions_oidc is false (D-0036)."
  value       = var.enable_github_actions_oidc ? azuread_application.github_actions[0].client_id : null
}

output "azure_tenant_id" {
  description = "Set as the AZURE_TENANT_ID repository variable in GitHub."
  value       = data.azurerm_client_config.current.tenant_id
}

output "azure_subscription_id" {
  description = "Set as the AZURE_SUBSCRIPTION_ID repository variable in GitHub."
  value       = data.azurerm_client_config.current.subscription_id
}

output "container_app_name" {
  description = "Set as the CONTAINER_APP_NAME repository variable in GitHub -- the deploy workflow's `az containerapp update` target."
  value       = azurerm_container_app.main.name
}

output "container_app_url" {
  description = "The live app URL, once GitHub Actions has deployed a real image over the placeholder."
  value       = "https://${azurerm_container_app.main.ingress[0].fqdn}"
}
