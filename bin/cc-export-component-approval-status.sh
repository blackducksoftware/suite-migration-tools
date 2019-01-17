#!/bin/sh

# Run this script on the Code Center DB server to output the KB components with their approval status
# and other information to the output file desired

OUTPUT_FILE=${1:-output.csv}
psql -qA -F '|' -d bds_catalog -o ${OUTPUT_FILE} -c 'select c.name,c.version,cl.kb_license_name as kbLicenseName,cl.kb_license_id as kbLicenseId,c.approval_status as status,c.kb_component_id as kbComponentId,c.kb_release_id as kbReleaseId from component c join component_license cl on (cl.component_id=c.id and cl.order_no=0) where c.kb_component_id is not null order by c.name,c.version ';