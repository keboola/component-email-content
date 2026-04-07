#!/usr/bin/env bash

set -e

# Check if the KBC_DEVELOPERPORTAL_APP environment variable is set
if [ -z "$KBC_DEVELOPERPORTAL_APP" ]; then
    echo "Error: KBC_DEVELOPERPORTAL_APP environment variable is not set."
    exit 1
fi

# Determine app-specific config directory (if any)
case "$KBC_DEVELOPERPORTAL_APP" in
  kds-team.ex-ms-outlook-email-content) CONFIG_DIR="component_config_ms_outlook" ;;
esac

# Resolve config file: check app-specific dir first, fall back to component_config
resolve_config_file() {
    local filename="$1"
    if [ -n "$CONFIG_DIR" ] && [ -f "$CONFIG_DIR/$filename" ]; then
        echo "$CONFIG_DIR/$filename"
    elif [ -f "component_config/$filename" ]; then
        echo "component_config/$filename"
    fi
}

# Pull the latest version of the developer portal CLI Docker image
docker pull quay.io/keboola/developer-portal-cli-v2:latest

# Function to update a property for the given app ID
update_property() {
    local app_id="$1"
    local prop_name="$2"
    local file_path="$3"

    if [ ! -f "$file_path" ]; then
        echo "File '$file_path' not found. Skipping update for property '$prop_name' of application '$app_id'."
        return
    fi

    # shellcheck disable=SC2155
    local value=$(<"$file_path")

    echo "Updating $prop_name for $app_id"
    echo "$value"

    if [ -n "$value" ]; then
        docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property "$KBC_DEVELOPERPORTAL_VENDOR" "$app_id" "$prop_name" --value="$value"
        echo "Property $prop_name updated successfully for $app_id"
    else
        echo "$prop_name is empty for $app_id, skipping..."
    fi
}

app_id="$KBC_DEVELOPERPORTAL_APP"

update_property "$app_id" "isDeployReady" "$(resolve_config_file isDeployReady.md)"
update_property "$app_id" "longDescription" "$(resolve_config_file component_long_description.md)"
update_property "$app_id" "configurationSchema" "$(resolve_config_file configSchema.json)"
update_property "$app_id" "configurationRowSchema" "$(resolve_config_file configRowSchema.json)"
update_property "$app_id" "configurationDescription" "$(resolve_config_file configuration_description.md)"
update_property "$app_id" "shortDescription" "$(resolve_config_file component_short_description.md)"
update_property "$app_id" "logger" "$(resolve_config_file logger)"
update_property "$app_id" "loggerConfiguration" "$(resolve_config_file loggerConfiguration.json)"
update_property "$app_id" "licenseUrl" "$(resolve_config_file licenseUrl.md)"
update_property "$app_id" "documentationUrl" "$(resolve_config_file documentationUrl.md)"
update_property "$app_id" "sourceCodeUrl" "$(resolve_config_file sourceCodeUrl.md)"
update_property "$app_id" "uiOptions" "$(resolve_config_file uiOptions.md)"

# Update the actions.md file
source "$(dirname "$0")/fn_actions_md_update.sh"
update_property "$app_id" "actions" "$(resolve_config_file actions.md)"