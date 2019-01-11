'''
Created on January 8, 2019

@author: gsnyder

Processes snippet matches found in a given BD project-version, and using a Protex BOM import baseline version,
reconcile (and confirm) the snippet matches that correspond to files previously identified by the Protex BOM import

'''
from blackduck.HubRestApi import HubInstance, object_id
import sys
import json
import copy
import argparse

hub = HubInstance()

parser = argparse.ArgumentParser(description="Reconcile snippet matches that correspond to files already identified in a previously imported Protex BOM")
parser.add_argument('project_name', type=str, help='Name of the project that contains the version whose snippet matches we want to reconcile (and confirm)')
parser.add_argument('version_name', help="The version that contains the snippet matches we want to reconcile (and confirm), given the protex BOM import")
parser.add_argument('--protex_import_version', default='protex_bom_import', help="The Hub version label pointing to where the Protex BOM import was mapped to")
args = parser.parse_args()


# Get the Bom Components for a Project ID + Version ID Pair
# Returns the JSON representation from the HUB in object form
# def get_protex_import_bom_components(project_id, version_id): 
#     version = hub.get_version_by_id(project_id, version_id)
#     return hub.get_version_components(version)

# Takes the snippet entries from a Hub snippet-bom-entries request and organizes 
# them into a dictionary keyed by the path of the file the snippet was found in
def get_snippet_path_map(snippet_entries):
    snippet_map = {}
    for cur_snippet in snippet_entries['items']:
        path = cur_snippet['compositePath']['path']
        if path in snippet_map:
            print("Possible overwrite of snippet in map - more than on snippet for: ", path)
        snippet_map[path] = cur_snippet
    return snippet_map

# Takes a Bom Component representation + It's file data representation + the map of path -> Snippets
# Returns a dict that has keys as paths
# Each value in the map is the Bom Component that declares the path + the snippets that are for that Parth
def get_component_file_map_by_path(bom_component_json, component_files, snippets):
    component_path_map = {}
    for cur_file in component_files['items']:
        cur_path = cur_file['filePath']['path']
        if cur_path in snippets:
            component_path_map[cur_path] = (bom_component_json, snippets[cur_path])
    return component_path_map

# Prints a user visible report of a map from path -> component + snippets
# The argument for this is the output of get_component_file_map_by_path
# This report details what snippets the script is going to confirm
def print_snippet_component_report(component_snippet_by_path_map):
    print("******************* Snippet -> Component potential matches ********************************")
    if not component_snippet_by_path_map:
        print("No Snippets or Components")
    for cur_path in component_snippet_by_path_map:
        cur_component_candidate = component_snippet_by_path_map[cur_path][0]
        cur_snippet = component_snippet_by_path_map[cur_path][1]
        print(cur_path, ": ")
        print("--------------------Component: ")
        #print(json.dumps(cur_component_candidate, indent=2))
        print("Component Name: ", cur_component_candidate['componentName'])
        print("Component Version: ", cur_component_candidate['componentVersionName'])
        print("Un-reconciled Snippets: Present")
        #print(json.dumps(cur_snippet, indent=2))
        print("***************************************************************************************")
    print()

# Gets the file paths that a snippet-bom-entries response represents
# This returns a flattened set of paths represented by the snippets
def getSnippetNames(snippet_bom_entries):
    files = set()
    for cur_item in snippet_bom_entries['items']:
        files.add(str(cur_item['name'] + " - " + cur_item['compositePath']['path']))
    return files

# Reconcile Snippets for a given Hub Release ID
# Takes 2 parameters:
# The first is the Hub Version ID (project ID not needed)
# The second is a dict from path -> component + snippets
# The component in this case is the component that already declares the snippets.
# Returns the # of entries that were sent to the Hub to reconcile
def reconcile_snippet_matches(target_project_id, target_version_id, component_snippet_by_path_map):
    map_copy = copy.deepcopy(component_snippet_by_path_map)
    snippets_reconciled = 0
    for cur_path in map_copy:
        print("Confirming snippet for path: ", cur_path)
        cur_component_candidate = map_copy[cur_path][0]
        cur_snippet = map_copy[cur_path][1]
        cur_num_snippet_bom_entries = len(cur_snippet['fileSnippetBomComponents'])
        #print("Component in place:")
        print("# Snippet entries to reconcile: ", cur_num_snippet_bom_entries)
        #print(cur_component_candidate)
        #print("Snippet to reconcile: ")
        #print(cur_snippet)
        if cur_component_candidate is not None and cur_snippet is not None:
            alternate_match = hub.find_matching_alternative_snippet_match(target_project_id, target_version_id, cur_snippet, cur_component_candidate)
            if alternate_match:
                # Update the snippet match to use the alternate
                response = hub.update_snippet_match(target_version_id, cur_snippet, alternate_match)
            
            # Otherwise, confirm the match using the "best match" the Hub suggests

            # TODO: Edit the snippet match to use the component-version from Protex 
            cur_status = hub.confirm_snippet_bom_entry(target_version_id, cur_snippet)
            if cur_status == 1:
                print("SUCCESS")
            else:
                print("FAILED: ", cur_status)
            snippets_reconciled = snippets_reconciled   + cur_status
            
    return snippets_reconciled 

# Returns the set of paths in the files entry for a component
# This is a flattened set, the set will contain duplicates if the Hub has multiple usages in the BOM for 
# the same path
def get_paths_for_component_files_entry(component_files_entry):
    paths = set()
    for cur_item in component_files_entry['items']:
        paths.add(cur_item['filePath']['path'])
    return paths

# Process a single component in a BOM and reconcile snippets that match a file already declared in the BOM
# Args:
#   Hub Project ID
#   Hub Version ID
#   BOM Component to process
#   Dict of Paths -> Snippets
# Returns the total # of snippets that were requested to be reconciled
def process_bom_component(project_id, protex_import_version_id, target_version_id, bom_component, snippet_path_map):
    # TODO: Fix this, a bom component given here might or might not have a component-version
    item_link = bom_component['_meta']['href']

    print("*******************************************************")
    component_id = item_link.split("/")[-3]
    component_version_id = item_link.split("/")[-1]
    
    print('Processing:')
    if 'componentVersionName' in bom_component:
        print(bom_component['componentName'], ": ", bom_component['componentVersionName'])
    else:
        print(bom_component['componentName'])
    
    component_files_json = hub.get_file_matches_for_component_with_version(
        project_id, protex_import_version_id, component_id, component_version_id)  
    
    print("File paths associated with this component: ")
    for path in get_paths_for_component_files_entry(component_files_json):
        print(path)
    
    component_by_file_map = get_component_file_map_by_path(bom_component, component_files_json, snippet_path_map)
    print_snippet_component_report(component_by_file_map)

    if len(component_by_file_map) > 0:
        # return len(component_by_file_map)
        return reconcile_snippet_matches(project_id, target_version_id, component_by_file_map)
    
    return 0


# Main method
def main():
    target_project = hub.get_project_by_name(args.project_name)
    if not target_project:
        print("Project ", args.project_name, " not found.")
        sys.exit(1)

    print("Found target project {}".format(args.project_name))

    target_version = hub.get_version_by_name(target_project, args.version_name)
    protex_import_version = hub.get_version_by_name(target_project, args.protex_import_version)

    if not target_version:
        print("Version {} not found for project {}".format(args.version_name, args.project_name))
        sys.exit(1)

    print("Found target version {} in project {}".format(args.version_name, args.project_name))

    if not protex_import_version:
        print("Protex import version {} not found for project {}".format(args.protex_import_version, args.project_name))
        sys.exit(1)

    print("Found protex import version {} in project {}".format(args.protex_import_version, args.project_name))

    target_project_id = object_id(target_project)
    target_version_id = object_id(target_version)
    protex_import_version_id = object_id(protex_import_version)

    ########
    #
    # Get Snippets from the target version and map them by their source path
    #
    ########
    snippet_data = hub.get_snippet_bom_entries(target_project_id, target_version_id)
    # TODO: len(snippet_data['items']) showing 43 snippet matches when in the GUI it shows 44, hmmm...
    snippet_path_map = get_snippet_path_map(snippet_data)
            
    print("***********Project Snippets ***************************")
    print("# Snippet Files: ", snippet_data['totalCount'])
    print("Snippet file list:")
    for file in getSnippetNames(snippet_data):
        print(file)

    #######
    #
    # Confirm the snippets if the files they go with match files in the Protex BOM components (i.e. the source
    # files within the Protex BOM) 
    #
    #######
    protex_components = hub.get_version_components(protex_import_version)
    total_snippets_confirmed = 0
    
    for cur_item in protex_components['items']:
        total_snippets_confirmed = total_snippets_confirmed + process_bom_component(
            target_project_id, protex_import_version_id, target_version_id, cur_item, snippet_path_map)

    print("Confirmed: {} snippets for project {}, version {}, using Protex BOM import {}".format(
        total_snippets_confirmed, args.project_name, args.version_name, args.protex_import_version))
    
if __name__ == "__main__":
    main()

        



