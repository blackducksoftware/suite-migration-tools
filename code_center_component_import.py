#!/usr/bin/env python

import csv
import logging
from pprint import pprint

from blackduck.HubRestApi import HubInstance

class ApprovalStatusConflict(Exception):
	pass


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
		'''Given a Protex component info (component id, release id, approval status) import the component
		approval into the Black Duck Hub.

		The steps include:
		- Looking up the corresponding Hub KB component id, version id
		- Comparing the approval statuses to see if there is a change
		- Updating the Hub component approval status accordingly

		The KB's for Protex and the Hub are not the same so in some (rare) cases the lookup will fail.

		Returns a result which will be one of "Updated", "Equal" (no action), or "Failed"
		'''
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

	def _get_protex_info(self, suite_component_info):
		'''Given a row from the CSV file, with the Suite component info, return the Protex
		component id, release/version id, and approval status
		'''
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
		component_id, version_id, approval_status = self._get_protex_info(suite_component_info)
		return self._update_approval_status(component_id, approval_status, version_id)

	def _set_hub_component_to_unreviewd(self, suite_component_info):
		protex_component_id, protex_release_id, protex_approval_status = self._get_protex_info(suite_component_info)
		# overwrite the approval status to un-reviewed
		protex_approval_status = 'NOT_REVIEWED'
		return self._update_approval_status(protex_component_id, protex_approval_status, protex_release_id)

	def reset_components_to_unreviewed(self):
		'''Parse a given CSV file and reset the approval status (in Hub) for any components found
		'''
		with open(args.component_approval_status_export, newline='') as component_list_file:
			reader = csv.DictReader(component_list_file, delimiter="|")
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

	def _reconcile_component_approvals(self, component_name_and_version, component_approvals):
		# Given a list of component approvals (for the same component/name), determine if there is
		# any conflict in the approval status values and, if not, choose an appropriate record
		# to use for updating the Hub. 
		# Note that Protex/CC status values of 'PENDING', 'MOREINFO', 'NOTSUBMITTED' all map to UNREVIEWED
		statuses = set([c['approval_status'] for c in component_approvals])
		if 'REJECTED' in statuses and 'APPROVED' in statuses:
			raise ApprovalStatusConflict("component {} has conflicting status values ({})".format(
				component_name_and_version, component_approvals))
		elif 'APPROVED' in statuses:
			# Choose the first APPROVED
			suite_component_info = list(filter(
				lambda ca: ca['approval_status'] == 'APPROVED', component_approvals))[0]
		elif 'REJECTED' in statuses:
			# Choose the first REJECTED
			suite_component_info = list(filter(
				lambda ca: ca['approval_status'] == 'REJECTED', component_approvals))[0]
		else:
			# Choose the first in the list
			suite_component_info = component_approvals[0]
		return suite_component_info

	def import_components(self):
		'''Import component approvals from CC

		It is assumed that we have pulled the component approvals on a per-project basis so there can
		be more than one approval request per component. And if there are > 1 approval requests for
		any given component there is potentially a conflict which we must reconcile.
		'''
		with open(args.component_approval_status_export, newline='') as component_list_file:
			reader = csv.DictReader(component_list_file, delimiter="|")
			updated = []
			conflicts = []
			failed = []
			equivalent = []

			#
			# Read all rows from the CSV file to compile a list of all
			# component approval requests and create a set of component names/versions
			#
			all_rows_by_component_name_and_version = list()
			all_component_names_and_versions = set()
			for row in reader:
				# list of tuples, first element is the key (component_name:component_version), 2nd element is the 
				# row or suite_component_info 
				all_rows_by_component_name_and_version.append(
						("{}:{}".format(row['component_name'], row['component_version']), row)
					)
				# set of keys (component_name:component_version)
				all_component_names_and_versions.add(
					"{}:{}".format(row['component_name'], row['component_version']))

			#
			# look for any duplicate component approval requests and reconcile their approval status values 
			# to decide whether we can update the component approval status in the Hub
			#
			for component_name_and_version in all_component_names_and_versions:
				component_approvals = [
					r[1] for r in all_rows_by_component_name_and_version if component_name_and_version == r[0]]
				if len(component_approvals) == 1:
					suite_component_info = component_approvals[0]
				elif len(component_approvals) > 1:
					try:
						suite_component_info = self._reconcile_component_approvals(
							component_name_and_version, component_approvals)
					except ApprovalStatusConflict:
						conflicts.extend(component_approvals)
						logging.warning(
							"The component {} could not be imported due to an approval status conflict among the CC component approval requests ({})".format(
								component_name_and_version, component_approvals))
						continue
				else:
					logging.error("What? This is a bug cause we should never have 0 component approvals")
					continue

				#
				# Update the Hub component approval status
				#
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

			#
			# Dump the results
			#
			logging.info("Updated {} suite components or component versions".format(len(updated)))
			self._dump_updated_to_file(updated)

			if len(equivalent) > 0:
				logging.info("Did not update {} suite components because the approval status they map to is equal to the existing Hub component approval status".format(
					len(equivalent)))
				self._dump_equivalent_to_file(equivalent)

			if len(failed) > 0:
				logging.info("Failed to update {} suite components or component versions".format(len(failed)))
				self._dump_failed_to_file(failed)
			if len(conflicts) > 0:
				logging.info(
					"Skipped {} suite components or component versions because there were approval status conflicts".format(
						len(conflicts))
					)
				self._dump_conflicts(conflicts)

	def _dump_updated_to_file(self, updated):
		import pdb; pdb.set_trace()
		self._dump_to_file(updated, "-updated.csv")

	def _dump_failed_to_file(self, failed):
		self._dump_to_file(failed, "-failed.csv")

	def _dump_conflicts(self, conflicts):
		import pdb; pdb.set_trace()
		self._dump_to_file(conflicts, "-conflicts.csv")
		
	def _dump_equivalent_to_file(self, equivalent):
		self._dump_to_file(equivalent, "-equivalent.csv")
		
	def _dump_to_file(self, component_list, extension):
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













