# The Container App itself.
#
# Split of ownership, deliberately: Terraform creates this resource
# and everything around it (env vars, secret wiring, ingress,
# identity), but NEVER touches which image tag is running after first
# apply -- see the lifecycle block below. GitHub Actions owns that,
# via `az containerapp update --image` on every deploy (see
# .github/workflows/deploy.yml). Without this split, every
# `terraform apply` would silently roll the running app back to the
# placeholder image below, undoing whatever CI/CD had deployed.

resource "azurerm_container_app" "main" {
  name                         = "ca-${local.name_prefix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = "${azurerm_key_vault.main.vault_uri}secrets/anthropic-api-key"
    identity            = azurerm_user_assigned_identity.app.id
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.app.id
  }
  secret {
    name                = "share-token-secret"
    key_vault_secret_id = azurerm_key_vault_secret.share_token_secret.versionless_id
    identity            = azurerm_user_assigned_identity.app.id
  }

  template {
    container {
      name = "overture"
      # Placeholder, real Microsoft-published image -- exists only so
      # the Container App has something valid to start with on first
      # `apply`, before any GitHub Actions deploy has ever run.
      # GitHub Actions immediately replaces this with the real image.
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "LLM_PROVIDER"
        value = "anthropic"
      }
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "SHARE_TOKEN_SECRET"
        secret_name = "share-token-secret"
      }
      env {
        name  = "APP_INSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
    }

    min_replicas = 0 # scale-to-zero -- no traffic, no compute cost
    max_replicas = 1 # a portfolio demo has no need for horizontal scale
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  tags = local.common_tags
}
