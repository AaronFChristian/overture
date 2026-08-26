#!/usr/bin/env bash
# Manual deploy -- builds the image locally and pushes it using
# Aaron's own authenticated sessions (docker login to GHCR, az login
# to Azure), rather than through GitHub Actions.
#
# This exists specifically because SDSU's Entra ID tenant blocks this
# account from registering applications, which blocks the OIDC deploy
# path entirely -- confirmed via a direct `az ad app create` test,
# not assumed. See decisions.md D-0036, D-0037. The GitHub Actions
# workflow (.github/workflows/deploy.yml) stays in the repo, correct
# and ready, for any tenant that does permit app registration.
#
# Prerequisites, once:
#   docker login ghcr.io -u AaronFChristian
#     (needs a GitHub personal access token with write:packages scope --
#      GITHUB_TOKEN only works inside Actions runners, not locally)
#   Make the ghcr.io/aaronfchristian/overture package public after
#     the first push (D-0033), so Container Apps can pull it with no
#     registry credential.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_TAG="ghcr.io/aaronfchristian/overture:manual-$(date +%s)"

echo "Building $IMAGE_TAG ..."
# --platform linux/amd64 is required, not optional, when building on
# Apple Silicon (arm64): Docker otherwise builds for the host's own
# architecture, and Azure Container Apps runs on amd64 infrastructure
# only. Without this flag, the pushed image has no compatible layer
# for Azure to pull at all -- discovered via a real failed deploy,
# not anticipated in advance. See decisions.md D-0039.
docker build --platform linux/amd64 -t "$IMAGE_TAG" .

echo "Pushing $IMAGE_TAG ..."
docker push "$IMAGE_TAG"

RESOURCE_GROUP=$(cd terraform && terraform output -raw resource_group_name)
CONTAINER_APP=$(cd terraform && terraform output -raw container_app_name)

echo "Deploying $IMAGE_TAG to $CONTAINER_APP ..."
az containerapp update \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$IMAGE_TAG"

echo "Done. URL:"
cd terraform && terraform output -raw container_app_url
