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
