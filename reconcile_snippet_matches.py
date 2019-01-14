'''
Created on January 8, 2019

@author: gsnyder

Reconciles snippet matches in a BD Hub project-version against a project-version that was created from
a Protex BOM import

'''
from blackduck.HubRestApi import HubInstance, object_id
import sys
import json
import copy
import argparse
import logging

hub = HubInstance()

parser = argparse.ArgumentParser(
    description="Reconcile snippet matches in a BD Hub project-version against a project-version created by a Protex BOM import",
    formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument(
    'project_name', 
    help="""Name of the project that contains the version whose snippet matches we want to reconcile (and confirm), 
AND the Protex BOM import""")
parser.add_argument(
    'version_name', 
    help="The version that contains the snippet matches we want to reconcile (and confirm), given the protex BOM import")
parser.add_argument(
    '--protex_import_version', 
    default='protex_bom_import', 
    help="The Hub version label pointing to where the Protex BOM import was mapped to")
parser.add_argument(
    '--use_best_match', 
    action='store_true', 
    help="""If the Protex BOM import component does not match any of the Hub snippet match components, 
confirm the snippet using the Hub's 'best match'""")
parser.add_argument(
    '--override_snippet_component', 
    action='store_true', 
    help="""Override the snippet match component info with the component info from the Protex BOM import if the Hub 
snippet matches do not contain an equivalent component. \nWARNING: Snippet source file info will be disassociated so use with care.""")
args = parser.parse_args()


# Get the Bom Components for a Project ID + Version ID Pair
# Returns the JSON representation from the HUB in object form
# def get_protex_import_bom_components(project_id, version_id): 
#     version = hub.get_version_by_id(project_id, version_id)
#     return hub.get_version_components(version)



def get_snippet_path_map(snippet_entries):
    # Build a map by snippet source file path for all the snippet matches in the given snippet bom entries object
    snippet_map = {}
    for cur_snippet in snippet_entries['items']:
        path = cur_snippet['compositePath']['path']
        if path in snippet_map:
            logging.debug("Possible overwrite of snippet in map - more than on snippet for: ", path)
        snippet_map[path] = cur_snippet
    return snippet_map

def get_component_file_map_by_path(bom_component_json, component_files, snippets):
    # Find the intersection of source file paths in the component_files object
    # with the source file paths in the given snippet matches map
    # and build/return a new map that merges/associates the given bom component info with the snippet match info
    component_path_map = {}
    for cur_file in component_files['items']:
        source_file_path = cur_file['filePath']['path']
        if source_file_path in snippets:
            component_path_map[source_file_path] = (bom_component_json, snippets[source_file_path])
    return component_path_map

def get_snippet_name_and_file_path(snippet_bom_entry):
    return str(snippet_bom_entry['name'] + " - " + snippet_bom_entry['compositePath']['path'])

def get_snippet_names_and_file_paths(snippet_bom_entries):
    # Gets the file paths that a snippet-bom-entries response represents
    # This returns a flattened set of paths represented by the snippets
    files = set()
    for snippet_bom_entry in snippet_bom_entries['items']:
        files.add(get_snippet_name_and_file_path(snippet_bom_entry))
    return files

def same_component(bom_component, snippet_match_component):
    b_name, b_version_name, b_id, b_version_id = bom_component_info(bom_component)
    s_name, s_version_name, s_id, s_version_id = snippet_component_info(snippet_match_component)

    if b_name == s_name and b_version_name == s_version_name:
        return True
    else:
        return False

def snippet_component_info(snippet_match_component):
    name = snippet_match_component['project']['name']
    component_id = snippet_match_component['project']['id']
    version_name = snippet_match_component['release']['version']
    version_id = snippet_match_component['release']['id']
    return (name, version_name, component_id, version_id)

def bom_component_info(bom_component):
    component_name = bom_component['componentName']
    component_id = bom_component['component'].split("/")[-1]
    if 'componentVersionName' in bom_component:
        component_version_name = bom_component['componentVersionName']
    else:
        component_version_name = None
    if 'componentVersion' in bom_component:
        component_version_id = bom_component['componentVersion'].split("/")[-1]
    else:
        component_version_id = None
    return (component_name, component_version_name, component_id, component_version_id)

def reconcile_snippet_matches(
    target_project_id, 
    target_version_id, 
    hub_snippet_matches_by_file_path, 
    override_snippet_component=False, 
    use_best_match=False):
    # Reconcile the snippet matches in the given hub_snippet_matches_by_file_path map/dict
    #   map/dict structure is expected to be,
    #       source_file_path -> (protex_bom_component_info, hub snippet match info)
    #
    #   To reconcile, we compare the protex bom component to the snippet match component
    #       If they are equal, we confirm the snippet using its current component info which (the 'best match' as designated by the Hub)
    #       If they are not equal, we look at the alternative snippet matches and their components
    #           If we find an equivalent component in one of the alternative matches, we confirm using that one
    #           If no equivalent was found, and use_best_match is True, use the Hub's best match to confirm the snippet
    #           Otherwise, if override_snippet_component is True, we confirm the snippet match after
    #               overriding the snippet match component info with the component info from protex
    #               The consequence of this is the snippet match will NOT have source file info associated with it
    #           If override_snippet_component is false, we skip the snippet match to allow the user to reconcile it manually
    # 
    logging.debug("Attempting to reconcile {} snippet matches".format(len(hub_snippet_matches_by_file_path)))


    snippets_reconciled = 0
    for source_file_path in hub_snippet_matches_by_file_path:

        protex_bom_component = hub_snippet_matches_by_file_path[source_file_path][0]
        cur_snippet = hub_snippet_matches_by_file_path[source_file_path][1]

        assert protex_bom_component is not None, "There should always be a Protex bom component to reconcile against"
        assert cur_snippet is not None, "We need a snippet match to reconcile"

        assert 'fileSnippetBomComponents' in cur_snippet, "A valid snippet match must have a fileSnippetBomComponents"
        assert len(cur_snippet['fileSnippetBomComponents']) == 1, "We can only reconcile one snippet match at a time"
        assert 'reviewStatus' in cur_snippet['fileSnippetBomComponents'][0], "A snippet match must have a reviewStatus"

        pbc_name, pbc_version_name, pbc_id, pbc_version_id = bom_component_info(protex_bom_component)
        protex_bom_component_desc_str = "{}:{}".format(pbc_name, pbc_version_name)

        logging.debug("Reconciling/confirming snippet {} for path {}".format(cur_snippet['name'], source_file_path))
        cur_num_snippet_bom_entries = len(cur_snippet['fileSnippetBomComponents'])

        snippet_match_component = cur_snippet['fileSnippetBomComponents'][0]
        if snippet_match_component['reviewStatus'] != "NOT_REVIEWED":
            logging.info("Snippet match {} has already been reviewed. Skipping...".format(get_snippet_name_and_file_path(cur_snippet)))
            continue
        else:
            logging.debug("Snippet match {} has not been reviewed, proceeding to reconcile".format(
                get_snippet_name_and_file_path(cur_snippet)))

        if not same_component(protex_bom_component, snippet_match_component):
            try:
                alternate_match_component = hub.find_matching_alternative_snippet_match(target_project_id, target_version_id, cur_snippet, protex_bom_component)
            except:
                logging.error("Failed to find an alternative snippet match for Protex component {} due to an exception".format(
                    protex_bom_component_desc_str), exc_info=True)
                alternate_match_component = False
            if alternate_match_component:
                logging.debug("Found an alternate snippet match with the same OS component as the protex bom component")
                try:
                    result = hub.update_snippet_match(target_version_id, cur_snippet, alternate_match_component)
                except:
                    logging.error("Failed to update the snippet match selection with the alternate match component info due to an exception. Skipping...")
                    continue
                else:
                    logging.debug("Updated snippet match with component info from alternate snippet match")
            elif use_best_match:
                logging.debug("The Protex BOM import component did not equal the snippet match component, and no alternative match was found. Using the Hub's 'best match' to confirm the snippet.")
            elif override_snippet_component:
                # Override the snippet component info with the protex bom component info
                logging.debug("Overriding the snippet component info with the protex bom component {}".format(protex_bom_component_desc_str))
                try:
                    result = hub.edit_snippet_bom_entry(target_version_id, cur_snippet, protex_bom_component)
                except:
                    logging.error("Failed to edit the current snippet match ({}) to use the Protex bom component {} due to an exception. Skipping this snippet match...".format(
                        cur_snippet['name'], protex_bom_component_desc_str), exc_info=True)
                    continue
            else:
                logging.warn(
                    "We did not find a snippet match with a component equal to the Protex component {}, and override_snippet_component was False. Skipping the snippet match".format(protex_bom_component_desc_str))
                continue

        try:
            cur_status = hub.confirm_snippet_bom_entry(target_version_id, cur_snippet)
        except:
            logging.error("Failed to confirm the snippet match due to an exception", exc_info=True)
            cur_status = 0

        if cur_status == 1:
            logging.info("SUCCESS - confirmed snippet {} using Protex BOM component {}".format(
                cur_snippet['name'], protex_bom_component_desc_str))
        else:
            logging.warn("FAILED - did NOT confirm snippet {} using Protex BOM component {}".format(
                cur_snippet['name'], protex_bom_component_desc_str))
        snippets_reconciled = snippets_reconciled + cur_status

    return snippets_reconciled 

def get_paths_for_component_files_entry(component_files_entry):
    # Returns the set of paths in the files entry for a component
    # This is a flattened set, the set will contain duplicates if the Hub has multiple usages in the BOM for 
    # the same path
    paths = set()
    for cur_item in component_files_entry['items']:
        paths.add(cur_item['filePath']['path'])
    return paths

# def print_snippet_component_report(hub_snippet_matches_by_file_path):
#     logging.debug("******************* Snippet -> Component potential matches ********************************")
#     if not hub_snippet_matches_by_file_path:
#         logging.debug("No Snippets or Components")
#     for cur_path in hub_snippet_matches_by_file_path:
#         protex_bom_component = hub_snippet_matches_by_file_path[cur_path][0]
#         cur_snippet = hub_snippet_matches_by_file_path[cur_path][1]
#         logging.debug(cur_path, ": ")
#         logging.debug("--------------------Component: ")
#         #logging.debug(json.dumps(protex_bom_component, indent=2))
#         logging.debug("Component Name: ", protex_bom_component['componentName'])
#         logging.debug("Component Version: ", protex_bom_component['componentVersionName'])
#         logging.debug("Un-reconciled Snippets: Present")
#         #logging.debug(json.dumps(cur_snippet, indent=2))
#         logging.debug("***************************************************************************************")
#     logging.debug()

def process_bom_component(
    project_id, 
    target_version_id, 
    protex_import_version_id, 
    protex_bom_component, 
    snippet_path_map, 
    override_snippet_component=False,
    use_best_match=False):
    # Process a single component in a BOM and reconcile snippets that match a file already declared in the BOM
    # Args:
    #   Hub Project ID
    #   Hub Version ID
    #   Protex BOM export/import version id
    #   Protex BOM Component to process
    #   Dict of Paths -> Snippets
    # Returns the total # of snippets that were reconciled/confirmed
    protex_component_name, protex_version_name, protex_component_id, protex_bom_component_version_id = bom_component_info(protex_bom_component)

    if protex_version_name:
        protex_component_str = "{}:{}".format(protex_component_name, protex_version_name)
    else:
        protex_component_str = "{}".format(protex_component_name)
    
    logging.debug("Processing {}".format(protex_component_str))

    protex_bom_component_files = hub.get_file_matches_for_component_with_version(
        project_id, protex_import_version_id, protex_component_id, protex_bom_component_version_id)  
    
    if 'items' in protex_bom_component_files and len(protex_bom_component_files['items']) > 0:
        logging.debug("Found {} paths associated with {}".format(len(protex_bom_component_files['items']), protex_component_str))

        logging.debug("File paths associated with this Protex component: ")
        for path in get_paths_for_component_files_entry(protex_bom_component_files):
            logging.debug(path)
        
        component_by_file_map = get_component_file_map_by_path(protex_bom_component, protex_bom_component_files, snippet_path_map)

        logging.debug("Found {} snippet matches whose source file path corresponds to source file paths in Protex component {}".format(
            len(component_by_file_map), protex_component_str))

        # print_snippet_component_report(component_by_file_map)

        if len(component_by_file_map) > 0:
            return reconcile_snippet_matches(
                project_id, 
                target_version_id, 
                component_by_file_map, 
                override_snippet_component=override_snippet_component,
                use_best_match=use_best_match)
    else:
        logging.debug("Did not find any source file paths associated with {}".format(protex_component_str))
    return 0


# Main method
def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    target_project = hub.get_project_by_name(args.project_name)
    if not target_project:
        logging.error("Project {} not found.".format(args.project_name))
        sys.exit(1)

    logging.debug("Found target project {}".format(args.project_name))

    target_version = hub.get_version_by_name(target_project, args.version_name)
    protex_import_version = hub.get_version_by_name(target_project, args.protex_import_version)

    if not target_version:
        logging.debug("Version {} not found for project {}".format(args.version_name, args.project_name))
        sys.exit(1)

    logging.debug("Found target version {} in project {}".format(args.version_name, args.project_name))

    if not protex_import_version:
        logging.debug("Protex import version {} not found for project {}".format(args.protex_import_version, args.project_name))
        sys.exit(1)

    logging.debug("Found protex import version {} in project {}".format(args.protex_import_version, args.project_name))

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
            
    logging.debug("***********Project Snippets ***************************")
    logging.debug("# Snippet Files: {}".format(snippet_data['totalCount']))
    logging.debug("Snippet file list:")
    for snippet_name_and_file_path in get_snippet_names_and_file_paths(snippet_data):
        logging.debug(snippet_name_and_file_path)

    #######
    #
    # Confirm the snippets if the files they go with match files in the Protex BOM components (i.e. the source
    # files within the Protex BOM) 
    #
    #######
    protex_components = hub.get_version_components(protex_import_version)
    total_snippets_confirmed = 0
    
    for protext_bom_component in protex_components['items']:
        total_snippets_confirmed = total_snippets_confirmed + process_bom_component(
            target_project_id, target_version_id, protex_import_version_id, protext_bom_component, snippet_path_map, \
            override_snippet_component=args.override_snippet_component, use_best_match=args.use_best_match)

    logging.debug("Confirmed: {} snippets for project {}, version {}, using Protex BOM import {}".format(
        total_snippets_confirmed, args.project_name, args.version_name, args.protex_import_version))
    
if __name__ == "__main__":
    main()

        



