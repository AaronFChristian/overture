# GitHub Actions OIDC federation.
#
# This is machine-to-machine identity for the deploy pipeline -- NOT
# the user-facing login (MSAL) that a future SE console will use.
# That's deliberately deferred to session 9, once there's a frontend
# to log into. See decisions.md D-0022 and D-0031.
#
# How this actually avoids storing a secret: GitHub's Actions runner
# generates a short-lived, cryptographically signed OIDC token at
# workflow-run time, scoped to a specific repo/branch/event. Azure AD
# is configured (via the federated identity credential below) to
# trust tokens signed by GitHub for THIS repo specifically, and
# exchanges a valid one for a short-lived Azure access token. Nothing
# long-lived or secret ever needs to exist in GitHub's secret store.

resource "azuread_application" "github_actions" {
  count = var.enable_github_actions_oidc ? 1 : 0

  display_name = "${local.name_prefix}-github-actions-deploy"
}

resource "azuread_service_principal" "github_actions" {
  count = var.enable_github_actions_oidc ? 1 : 0

  client_id = azuread_application.github_actions[0].client_id
}

resource "azuread_application_federated_identity_credential" "github_actions_main" {
  count = var.enable_github_actions_oidc ? 1 : 0

  application_id = azuread_application.github_actions[0].id
  display_name   = "github-actions-main-branch"
  description    = "Allows GitHub Actions workflow runs on ${var.github_repo}'s main branch to deploy."
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "github_actions_deploy" {
  count = var.enable_github_actions_oidc ? 1 : 0

  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions[0].object_id
}
