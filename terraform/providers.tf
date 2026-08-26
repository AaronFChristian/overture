terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # No remote backend -- state is local, on Aaron's machine only. See
  # decisions.md D-0025 for why: this is a single-developer,
  # ephemeral (build -> record -> destroy) project, and a remote
  # backend would mean provisioning and paying for a Storage Account
  # purely to hold state for infrastructure that mostly doesn't exist
  # between sessions anyway.
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

data "azurerm_client_config" "current" {}
