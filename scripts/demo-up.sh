#!/usr/bin/env bash
# Stands up the Azure landing zone. Deliberately does NOT pass
# -auto-approve to `terraform apply` -- you still see and confirm the
# plan yourself. This script saves you `cd`-ing and remembering the
# right command, not the judgment call of reviewing what's about to
# be created.
set -euo pipefail

cd "$(dirname "$0")/../terraform"

if [ ! -f terraform.tfvars ]; then
  echo "terraform.tfvars not found. Copy terraform.tfvars.example to" >&2
  echo "terraform.tfvars and fill in your real values first." >&2
  exit 1
fi

terraform init -input=false
terraform plan -out=tfplan
echo ""
echo "Review the plan above. Run 'terraform apply tfplan' to proceed,"
echo "or re-run this script after making changes."
