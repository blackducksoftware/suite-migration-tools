#!/bin/bash

export SCAN_PROTEX_CLI_PATH=${SCAN_PROTEX_CLI_PATH:-/Users/gsnyder/Projects/suite_migration_tools/scan.protex.cli-2018.11.1/bin}
PATH=${PATH}:${SCAN_PROTEX_CLI_PATH}

export EXPORT_SCRIPT=scan.protex.cli.sh

if [ -z "$(which ${EXPORT_SCRIPT})" ]; then
	echo "The ${EXPORT_SCRIPT} must be on your PATH for this to work. Set SCAN_PROTEX_CLI_PATH to point to the 'bin' folder where ${EXPORT_SCRIPT} resides."
	echo "The Protex BOM export tool can be downloaded from your Hub server at .../download/scan.protex.cli.zip"
	echo "e.g. wget https://hub-server/download/scan.protex.cli.zip"
	exit 1
fi

export PROTEX_SERVER_HOST=${1:-imp-px02.dc1.lan}
export PROTEX_SERVER_PORT=${2:-443}
export PROTEX_USERNAME=${3:-gsnyder@synopsys.com}
export PROTEX_PROJECT_NAME=${4:-c_pmullin_tutorial_5192}
export OUTPUT_DIR=${5:-./}
export OUTPUT_FILE_NAME=${6:-protex_bom_export.json}

echo "Exporting ${PROTEX_PROJECT_NAME} from server ${PROTEX_SERVER_HOST}"
scan.protex.cli.sh \
--address ${PROTEX_SERVER_HOST}:${PROTEX_SERVER_PORT} \
--project ${PROTEX_PROJECT_NAME} \
--user ${PROTEX_USERNAME} \
--include-files --dryRunWriteDir ${OUTPUT_DIR} \
--output ${OUTPUT_FILE_NAME} --secure --verbose
echo "Done exporting BOM info to ${PROTEX_PROJECT_NAME}"