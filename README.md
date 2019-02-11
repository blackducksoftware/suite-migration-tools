# Suite Migration Tools

Tools to help with migrating from Black Duck Suite (Protex, Code Center) to Black Duck Hub

* (KB) Component approval status migration
* Snippet identification migration

## Requirements

* Python 3+
* BD Hub v2018.12+ (earlier versions, e.g. v4, v5, or v2018.11.x might also work, but have not been tested)
* Protex 7.8+
* Code Center (CC) 7.4+

The user of these tools needs to be reaonsably proficient with:
* Protex, 
* CC, 
* BD Hub - especially, scans, project-versions, snippets, and component management 
* python 
* bash (or Bourne) shell
* working from the command line.

## Component approval status migration

Customers want to preserve the time invested in marking their KB components and component versions (or releases) as APPROVED, REJECTED, etc by exporting them from Code Center (CC) and importing them into the Black Duck Hub. Use the following to migrate (KB) component and component version approval status.

### How to export and import CC KB component approval status into the Hub

1. Export from CC using cc-export-project-component-approvals.sh on your CC DB server
	* This script includes the psql command you should run on your CC DB server machine to generate a pipe-delimited file with all the KB components and their approval status.
	* The script creates a pipe (|) delimited CSV file with the KB components and their approval status info, along with other info
1. Import the file contents to your Black Duck Hub server using code_center_component_import.py as follows using python3/pip3,

```
pip install blackduck
cat > .restconfig.json <<EOF
{
   "baseurl": "https://your-hub-server-host-name-or-ip",
   "username": "hub-username",
   "password": "hub-password",
   "insecure": true,
   "debug": false	
}
EOF
python code_center_component_import.py <name-of-pipe-delimited-file-from-step-1>
```

code_center_component_import.py uses the _blackduck_ python package to communicate with the Black Duck Hub's REST API and update the component approval status for all the components and component versions in the file. The _blackduck_ package gets the Hub URL and authentication information from the *.restconfig.json* file created above.

The tool will parse the CSV file, reading the components and their approval status info and then:

* Summarize the results
* Will dump the component info into files for further analysis/processing as required

Here's an excerpt of the output:

```
MainThread: 2019-02-11 11:48:40,303: INFO: Updated 1956 suite components or component versions
MainThread: 2019-02-11 11:48:40,331: INFO: Dumped 1956 components into sample-data/code-center-export-02-05-2019-updated.csv
MainThread: 2019-02-11 11:48:40,331: INFO: Did not update 598 suite components because the approval status they map to is equal to the existing Hub component approval status
MainThread: 2019-02-11 11:48:40,338: INFO: Dumped 598 components into sample-data/code-center-export-02-05-2019-equivalent.csv
MainThread: 2019-02-11 11:48:40,338: INFO: Failed to update 71 suite components or component versions
MainThread: 2019-02-11 11:48:40,339: INFO: Dumped 71 components into sample-data/code-center-export-02-05-2019-failed.csv
```



## Snippet reconciliation

Customers who previously identified OSS components using Protex, and (Protex) snippets, would like to preserve this work by importing the Protex BOM into the Hub which they can do using the Protex BOM import tool (aka scan.protex.cli). 

After importing the Protex BOM, however, the first Hub scan of the same project will produce (different) snippet matches which some customers will want to reconcile against the Protex BOM export/import. This reconcile snippet matches utility allows the user to reconcile snippet matches in a BD Hub project-version against another project-version that was created using a Protex BOM export.

### Key Considerations

* File hash values are not available through the BD (Hub) REST API (as of today, Jan 14, 2019), and so the (reconciliation) utility uses file paths and file names from the BD (Hub) scan to match against the files associated with the Protex BOM
	* i.e. If files have been moved or renamed they will not match
	* If files have been edited they could match, perhaps causing skewed results
* If the Protex user made incorrect choices for component matches, then those errors could be propagated. 
	* In some cases it might be advisable to forego the use of this utility, i.e. start fresh with the BD Hub scan

### Process overview

1. Export the Protex BOM using the scan.protex.cli.
	* Download the scan.protex.cli.zip from your Hub server at https://hub-hostname/download/scan.protex.cli.zip
	* Unpack the scan.protex.cli and use `create-protex-bom-export.bash` to create a Protex BOM export.
1. Create the Protex BOM export
1. Upload the Protex BOM export into the BD Hub
1. Map the resulting scan to a (Hub) project and version (use the version label = 'protex_bom_import' or record whatever name you used)
1. Do the BD Hub snippet scan to the same project, but using a different version (e.g. 1.0)
1. Run `reconcile_snippet_matches.py` to reconcile the snippet matches generated against the Protex BOM

# To run the Unit Tests

```
pip install -r requirements.txt
pytest
```

