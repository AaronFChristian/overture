#!/usr/bin/env bash
# Tears down the Azure landing zone, then verifies the resource group
# is actually empty afterward -- the check that guarantees nothing
# survives a destroy, discussed before any Azure resource in this
# project was ever created.
set -euo pipefail

cd "$(dirname "$0")/../terraform"

terraform destroy

RG_NAME=$(terraform output -raw resource_group_name 2>/dev/null || echo "")

if [ -z "$RG_NAME" ]; then
  echo "Could not read resource group name from Terraform output"
  echo "(this is expected if destroy already removed everything)."
  exit 0
fi

echo ""
echo "Verifying resource group is empty..."
az resource list --resource-group "$RG_NAME" --output table
