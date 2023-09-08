#!/usr/bin/env bash

set -e
# Obtain the component repository and log in
docker pull quay.io/keboola/developer-portal-cli-v2:latest


# Update properties in Keboola Developer Portal
echo "Updating ${KBC_DEVELOPERPORTAL_APP} long description"
value=`cat $COMPONENT_CONFIG_FOLDER/component_long_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} longDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} longDescription is empty!"
    exit 1
fi

echo "Updating ${KBC_DEVELOPERPORTAL_APP} config schema"
value=`cat $COMPONENT_CONFIG_FOLDER/configSchema.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} configurationSchema --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} configurationSchema is empty!"
fi

echo "Updating ${KBC_DEVELOPERPORTAL_APP} row config schema"
value=`cat $COMPONENT_CONFIG_FOLDER/configRowSchema.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} configurationRowSchema --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} configurationRowSchema is empty!"
fi


echo "Updating ${KBC_DEVELOPERPORTAL_APP} config description"

value=`cat $COMPONENT_CONFIG_FOLDER/configuration_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} configurationDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} configurationDescription is empty!"
fi


echo "Updating ${KBC_DEVELOPERPORTAL_APP} short description"

value=`cat $COMPONENT_CONFIG_FOLDER/component_short_description.md`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} shortDescription --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} shortDescription is empty!"
fi

echo "Updating ${KBC_DEVELOPERPORTAL_APP} logger settings"

value=`cat $COMPONENT_CONFIG_FOLDER/logger`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} logger --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} logger type is empty!"
fi

echo "Updating ${KBC_DEVELOPERPORTAL_APP} logger configuration"
value=`cat $COMPONENT_CONFIG_FOLDER/loggerConfiguration.json`
echo "$value"
if [ ! -z "$value" ]
then
    docker run --rm \
            -e KBC_DEVELOPERPORTAL_USERNAME \
            -e KBC_DEVELOPERPORTAL_PASSWORD \
            quay.io/keboola/developer-portal-cli-v2:latest \
            update-app-property ${KBC_DEVELOPERPORTAL_VENDOR} ${KBC_DEVELOPERPORTAL_APP} loggerConfiguration --value="$value"
else
    echo "${KBC_DEVELOPERPORTAL_APP} loggerConfiguration is empty!"
fi