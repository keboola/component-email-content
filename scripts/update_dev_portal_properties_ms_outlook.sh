#!/usr/bin/env bash

set -e
# Obtain the component repository and log in
docker pull quay.io/keboola/developer-portal-cli-v2:latest


# Update properties in Keboola Developer Portal
echo "Updating long description for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"
value=`cat component_config_ms_outlook/component_long_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} longDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} longDescription is empty!"
    exit 1
fi

echo "Updating config schema for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"
value=`cat component_config_ms_outlook/configSchema.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationSchema --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationSchema is empty!"
fi

echo "Updating row config schema for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"
value=`cat component_config_ms_outlook/configRowSchema.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationRowSchema --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationRowSchema is empty!"
fi


echo "Updating config description for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"

value=`cat component_config_ms_outlook/configuration_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} configurationDescription is empty!"
fi


echo "Updating short description for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"

value=`cat component_config_ms_outlook/component_short_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} shortDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} shortDescription is empty!"
fi

echo "Updating logger settings for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"

value=`cat component_config_ms_outlook/logger`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} logger --value="$value"
else
    echo "kds-team.ex-ms-outlook-email-content logger type is empty!"
fi

echo "Updating logger configuration for ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK}"
value=`cat component_config_ms_outlook/loggerConfiguration.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} loggerConfiguration --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP_MS_OUTLOOK} loggerConfiguration is empty!"
fi