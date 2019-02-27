import csv
import pytest

from blackduck.HubRestApi import HubInstance

# Add Parent path to the PYTHONPATH
import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir) 

from code_center_component_import import CodeCenterComponentImport, ApprovalStatusConflict

fake_hub_host = "https://my-hub-host"
fake_bearer_token = "aFakeToken"
default_hub_version = "2018.12.4"

@pytest.fixture()
def mock_hub_instance(requests_mock):
	def _create_hub_instance(hub_version=default_hub_version):
	    requests_mock.post(
	        "{}/j_spring_security_check".format(fake_hub_host), 
	        headers={"Set-Cookie": 'AUTHORIZATION_BEARER={}; Path=/; secure; Secure; HttpOnly'.format(fake_bearer_token)}
	    )
	    requests_mock.get(
	        "{}/api/current-version".format(fake_hub_host),
	        json = {
	            "version": hub_version,
	            "_meta": {
	                "allow": [
	                    "GET"
	                ],
	                "href": "{}/api/current-version".format(fake_hub_host)
	            }
	        }
	    )
	    return HubInstance(fake_hub_host, "a_username", "a_password")
	return _create_hub_instance

def test_construction(mock_hub_instance):
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	assert casef.component_approval_status_export_file == "a_file_name"
	assert casef.hub_instance == hub_instance

def test_get_protex_info(mock_hub_instance):
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-get-protex-info.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		row1 = next(reader)

		component_id, version_id, approval_status = casef._get_protex_info(row1)

		assert component_id == 'angularxqrcode3444828'
		assert version_id == '13663706'
		assert approval_status == 'APPROVED'

def test_reconciling_component_approvals_with_conflicts1(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-conflicts1.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		with pytest.raises(ApprovalStatusConflict) as e_info:
			casef._reconcile_component_approvals("slf4j-nop:2.0", rows)

def test_reconciling_component_approvals_with_approved1(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-approved1.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		suite_component_info = casef._reconcile_component_approvals("angularx-qrcode:1.2.4", rows)

		assert suite_component_info['approval_status'] == 'APPROVED'
		assert suite_component_info['component_name'] == 'angularx-qrcode'
		assert suite_component_info['component_version'] == '1.2.4'

def test_reconciling_component_approvals_with_more_than_one_approval(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-more-than-one-approval.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		suite_component_info = casef._reconcile_component_approvals("angularx-qrcode:1.2.4", rows)

		assert suite_component_info['approval_status'] == 'APPROVED'
		assert suite_component_info['component_name'] == 'angularx-qrcode'
		assert suite_component_info['component_version'] == '1.2.4'

def test_reconciling_component_approvals_with_rejected1(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-rejected1.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		suite_component_info = casef._reconcile_component_approvals("angularx-qrcode:1.2.4", rows)

		assert suite_component_info['approval_status'] == 'REJECTED'
		assert suite_component_info['component_name'] == 'angularx-qrcode'
		assert suite_component_info['component_version'] == '1.2.4'

def test_reconciling_component_approvals_with_more_than_one_rejection(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-more-than-one-rejection.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		suite_component_info = casef._reconcile_component_approvals("angularx-qrcode:1.2.4", rows)

		assert suite_component_info['approval_status'] == 'REJECTED'
		assert suite_component_info['component_name'] == 'angularx-qrcode'
		assert suite_component_info['component_version'] == '1.2.4'

def test_reconciling_component_approvals_with_no_accepted_or_rejected(mock_hub_instance):
	# single component with multiple approvals that conflict
	hub_instance = mock_hub_instance()
	casef = CodeCenterComponentImport("a_file_name", hub_instance)

	with open('test-no-accepted-or-rejected.csv') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='|')

		rows = [r for r in reader]

		suite_component_info = casef._reconcile_component_approvals("angularx-qrcode:1.2.4", rows)

		assert suite_component_info['approval_status'] == 'PENDING'
		assert suite_component_info['component_name'] == 'angularx-qrcode'
		assert suite_component_info['component_version'] == '1.2.4'


