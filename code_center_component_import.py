#!/usr/bin/env python

import csv
import logging
from pprint import pprint

from blackduck.HubRestApi import HubInstance


class CodeCenterComponentImport(object):
	# Map from Code Center (catalog) approval status to Black Duck Hub approval status
	# TODO: Finish mapping all the code center/protex components approval status values into Hub here
	APPROVAL_STATUS_MAP = {
		'NOT_REVIEWED': 'UNREVIEWED',
		'APPROVED': 'APPROVED',
		'PENDING': 'UNREVIEWED',
		'REJECTED': 'REJECTED',
		'MOREINFO': 'UNREVIEWED',
		'NOTSUBMITTED': 'UNREVIEWED'

	}
	COMPONENT_COL_NAME='component_name'
	# COMPONENT_TYPE_COL_NAME='ComponentType'
	VERSION_COL_NAME='component_version'
	LICENSE_COL_NAME='kb_license_name'
	# LICENSE_ID_COL_NAME='kblicenseid'
	APPROVAL_COL_NAME='approval_status'
	COMPONENT_ID_COL_NAME='kb_component_id'
	RELEASE_ID_COL_NAME='kb_release_id'

	SUPPORTED_COMPONENT_TYPES = ["STANDARD", "STANDARD_MODIFIED"]

	def __init__(self, component_approval_status_export_file, hub_instance):
		'''Expects a pipe-delimited ("|") file with a header row that includes the following fields (note the case and spaces in the names)
			- Component
			- Version
			- License
			- Approval Status
			- component id
			- release id
		'''
		self.component_approval_status_export_file = component_approval_status_export_file
		self.hub_instance = hub_instance

	def _update_approval_status(self, protex_component_id, protex_approval_status, protex_release_id=None):
		result = 'Failed'
		protex_release_id = None if protex_release_id == "null" else protex_release_id
		logging.debug("Searching for Protex component with ID {} and version ID {}".format(protex_component_id, protex_release_id))
		try:
			hub_component_info = self.hub_instance.find_component_info_for_protex_component(
					protex_component_id,
					protex_release_id
				)
			if hub_component_info:
				logging.debug("Found Hub component info for protex component id {} and release id {}: {}".format(
					protex_component_id, protex_release_id, hub_component_info))
				if 'version' in hub_component_info:
					details_url = hub_component_info['version']
				elif 'component' in hub_component_info:
					details_url = hub_component_info['component']
				else:
					logging.error("Hub component info ({}) did not contain either a component or version url".format(hub_component_info))
					return False

				component_or_version_details = self.hub_instance.get_component_by_url(details_url)

				if component_or_version_details and 'approvalStatus' in component_or_version_details:
					# logging.debug("Hub component or component version before update: {}".format(component_or_version_details))
					current_approval_status = component_or_version_details['approvalStatus']
					new_approval_status = CodeCenterComponentImport.APPROVAL_STATUS_MAP[protex_approval_status]

					if current_approval_status != new_approval_status:
						component_or_version_details['approvalStatus'] = new_approval_status
						logging.debug("Updating approval status (in Hub component/version) from {} to {}".format(
							current_approval_status, new_approval_status))
						response = self.hub_instance.update_component_by_url(details_url, component_or_version_details)
						if response.status_code == 200:
							result = "Updated"
							logging.info("Updated approval status to {}".format(new_approval_status))
						else:
							result = "Failed"
							logging.error("Failed to update approval status, status code: {}".format(response.status_code))
					else:
						result = "Equal"
						logging.debug("Current approval status and new are equal for (protex) component {}, release/version {}".format(
							protex_component_id, protex_release_id))
					
					component_or_version_details = self.hub_instance.get_component_by_url(details_url)
					logging.debug("approvalStatus after update: {}".format(component_or_version_details['approvalStatus']))
					# logging.debug("Hub component or component version after update: {}".format(component_or_version_details))
				else:
					logging.error("Hmm, that's odd, the Hub component/version didn't have an 'approvalStatus' field ({})".format(
						component_or_version_details))
			else:
				logging.warning('Could not locate Hub component or component version for Protex component id {} and release id {}'.format(protex_component_id, protex_release_id))
		except:
			logging.error(
				"Ooops. Something went very wrong for Protex component {}, release {}".format(protex_component_id, protex_release_id),
				exc_info=True)
			result = "Failed"
		finally:
			return result

	def _dump_updated_to_file(self, failed):
		self._dump_to_file(failed, "-updated.csv")

	def _dump_failed_to_file(self, failed):
		self._dump_to_file(failed, "-failed.csv")

	def _dump_skipped_to_file(self, skipped):
		self._dump_to_file(skipped, "-skipped.csv")
		
	def _dump_equivalent_to_file(self, equivalent):
		self._dump_to_file(equivalent, "-equivalent.csv")
		
	def _dump_to_file(self, component_list, extension):
		# import pdb; pdb.set_trace()
		dump_csv_file = self.component_approval_status_export_file.replace(".csv", extension)
		with open(dump_csv_file, 'w', newline='') as csvfile:
			fieldnames = [
				CodeCenterComponentImport.APPROVAL_COL_NAME,
				CodeCenterComponentImport.COMPONENT_COL_NAME,
				CodeCenterComponentImport.VERSION_COL_NAME,
				CodeCenterComponentImport.LICENSE_COL_NAME,
				'project_name',
				'project_version',
				'user_name',
				'first_name',
				'last_name',
				'time_submitted',
				CodeCenterComponentImport.COMPONENT_ID_COL_NAME,
				CodeCenterComponentImport.RELEASE_ID_COL_NAME,
				'catalogid',
				'projectid',
			]
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='|')
			writer.writeheader()
			for component in component_list:
				writer.writerow(component)
		logging.info("Dumped {} components into {}".format(len(component_list), dump_csv_file))

	def _get_protex_info(self, suite_component_info):
		try:
			component_id = suite_component_info[CodeCenterComponentImport.COMPONENT_ID_COL_NAME]
			version_id = suite_component_info[CodeCenterComponentImport.RELEASE_ID_COL_NAME]
			approval_status = suite_component_info[CodeCenterComponentImport.APPROVAL_COL_NAME]
		except KeyError:
			logging.error("Missing required key in component info ({}), skipping...".format(suite_component_info))
			return (None, None, None)
		else:
			return (component_id, version_id, approval_status)

	def _import_component(self, suite_component_info):
		# try:
		# 	component_id = suite_component_info[CodeCenterComponentImport.COMPONENT_ID_COL_NAME]
		# 	version_id = suite_component_info[CodeCenterComponentImport.RELEASE_ID_COL_NAME]
		# 	approval_status = suite_component_info[CodeCenterComponentImport.APPROVAL_COL_NAME]
		# except KeyError:
		# 	logging.error("Missing required key in component info ({}), skipping...".format(suite_component_info))
		# 	return False
		component_id, version_id, approval_status = self._get_protex_info(suite_component_info)
		return self._update_approval_status(component_id, approval_status, version_id)

	def _set_hub_component_to_unreviewd(self, suite_component_info):
		protex_component_id, protex_release_id, protex_approval_status = self._get_protex_info(suite_component_info)
		# overwrite the approval status to un-reviewed
		protex_approval_status = 'NOT_REVIEWED'
		return self._update_approval_status(protex_component_id, protex_approval_status, protex_release_id)

	def reset_components_to_unreviewed(self):
		with open(args.component_approval_status_export, newline='') as component_list_file:
			reader = csv.DictReader(component_list_file, delimiter="|")
			updated = []
			failed = []
			skipped = []
			for suite_component_info in reader:
				component_type = "STANDARD" 
				if component_type in CodeCenterComponentImport.SUPPORTED_COMPONENT_TYPES:
					try:
						self._set_hub_component_to_unreviewd(suite_component_info)
					except:
						logging.error("Failed to set component to unreviewed: {}".format(suite_component_info), exc_info=True)
				else:
					logging.debug("component type {} not in support component types ({})".format(
						component_type, CodeCenterComponentImport.SUPPORTED_COMPONENT_TYPES))

	def import_components(self):
		with open(args.component_approval_status_export, newline='') as component_list_file:
			reader = csv.DictReader(component_list_file, delimiter="|")
			updated = []
			failed = []
			equivalent = []
			skipped = []
			for suite_component_info in reader:
				import pdb; pdb.set_trace()
				# if component type not given, default to STANDARD (i.e. KB component)
				# component_type = suite_component_info.get(CodeCenterComponentImport.COMPONENT_TYPE_COL_NAME, "STANDARD")
				# TODO: Fix this once we have the component type info restored
				component_type = "STANDARD" 
				if component_type in CodeCenterComponentImport.SUPPORTED_COMPONENT_TYPES:
					import pdb; pdb.set_trace()
					logging.debug("Importing suite component: {}".format(suite_component_info))
					result = self._import_component(suite_component_info)
					if result == 'Updated':
						logging.info("Updated the Hub with suite component: {}".format(suite_component_info))
						updated.append(suite_component_info)
					elif result == 'Equal':
						logging.debug(
							"Suite component approval status in Protex is effectively equal to the Hub for component: {}".format(
								suite_component_info))
						equivalent.append(suite_component_info)
					else:
						logging.warn("Failed to update suite component: {}".format(suite_component_info))
						failed.append(suite_component_info)
				else:
					logging.debug("Skipping suite component because the type ({}) is not in supported types ({})".format(
						component_type, CodeCenterComponentImport.SUPPORTED_COMPONENT_TYPES))
					skipped.append(suite_component_info)

			logging.info("Updated {} suite components or component versions".format(len(updated)))
			self._dump_updated_to_file(updated)

			if len(equivalent) > 0:
				logging.info("Did not update {} suite components because the approval status they map to is equal to the existing Hub component approval status".format(
					len(equivalent)))
				self._dump_equivalent_to_file(equivalent)

			if len(failed) > 0:
				logging.info("Failed to update {} suite components or component versions".format(len(failed)))
				self._dump_failed_to_file(failed)
			if len(skipped) > 0:
				logging.info(
					"Skipped {} suite components or component versions because their type was not in {} types".format(
						len(skipped), CodeCenterComponentImport.SUPPORTED_COMPONENT_TYPES)
					)
				self._dump_skipped_to_file(skipped)

if __name__ == "__main__":
	import argparse
	import sys

	parser = argparse.ArgumentParser("Will read a pipe-delimited export from the Code Center catalog and import the component approval status information into Black Duck (Hub)")
	parser.add_argument("component_approval_status_export", help="Pipe-delimited file containing the component information from the Code Center catalog (i.e. global component approval statuses")
	parser.add_argument("-l", "--loglevel", choices=["CRITICAL", "DEBUG", "ERROR", "INFO", "WARNING"], default="DEBUG", help="Choose the desired logging level - CRITICAL, DEBUG, ERROR, INFO, or WARNING. (default: DEBUG)")
	parser.add_argument("-r", "--reset_approval_status", action='store_true', help="Reset the Hub component approval status (corresponding to the Protex component) to un-reviewed")
	args = parser.parse_args()

	logging_levels = {
		'CRITICAL': logging.CRITICAL,
		'DEBUG': logging.DEBUG,
		'ERROR': logging.ERROR,
		'INFO': logging.INFO,
		'WARNING': logging.WARNING,
	}
	logging.basicConfig(stream=sys.stdout, format='%(threadName)s: %(asctime)s: %(levelname)s: %(message)s', level=logging_levels[args.loglevel])
	logging.getLogger("requests").setLevel(logging.WARNING)
	logging.getLogger("urllib3").setLevel(logging.WARNING)

	hub = HubInstance()

	protex_importer = CodeCenterComponentImport(args.component_approval_status_export, hub)

	if args.reset_approval_status:
		logging.debug("resetting components to un-reviewed")
		protex_importer.reset_components_to_unreviewed()
	else:
		logging.debug("import component approval status")
		protex_importer.import_components()













