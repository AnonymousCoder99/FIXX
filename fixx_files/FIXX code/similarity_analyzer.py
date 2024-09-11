from similar_exploits import lift_node
from nltk.stem import PorterStemmer
import os
import json
import pickle
from migration_neo4j_4.neo4j_driver import *
from migration_neo4j_4.cypher_queries import *
from CypherQueries import *
import warnings
import globals
import csv

warnings.filterwarnings("ignore")
from CPGQueryInterface import CPGQueryInterface
qi = CPGQueryInterface()

uri = 'bolt://localhost:' + str(globals.NEO4J_BOLT_PORT)
user = 'neo4j'
password = 'user'
ABS_PATH = '/var/www/html/'
sim_details = open("/opt/project/results/codeastro/sim_details.txt", "a")
search_result = []
node_details2 = {}


class SimilarityAnalyzer:
    def __init__(self):
        self.driver = get_neo4j_driver()
        self.qi = CPGQueryInterface()
        self.identifier_occurrences = {}
        self.function_sensitivity_levels = {}

    # precount all occurrences of the different types of identifiers in an application.
    # Calculate sensitivity scores of functions (this can take a while)
    # Create clusters of identifiers
    # It needs to be done only once. Save results concrete file.
    def preprocess(self):
        #Create a file to store all the identifiers (list of code words) in the given application
        occurrences_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),"identifier_occurrences.pkl")
        os.system("touch " + occurrences_file_path)

        with open(occurrences_file_path, 'rb') as afile:
            #If the file is not empty, it means that step has been performed before
            #read the file and store all the data in the created array
            if os.path.getsize(occurrences_file_path) != 0:
                identifier_occurrences = pickle.load(afile)
                afile.close()
            else: #else leave it empty
                identifier_occurrences = {}

        if len(identifier_occurrences.items()) == 0:
                #count the number of function calls, methods, superglobals and other variables
            identifier_occurrences = self.qi.get_all_identifier_occurrences()
            afile = open(occurrences_file_path, 'wb')
            pickle.dump(identifier_occurrences, afile)
            afile.close()

        # read list of names of sensitive functions/instructions
        #this is provideed as input by the analyst
        sensitive_functions_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),"sensitive_functions.txt")
        sensitivity_file = open(sensitive_functions_file_path, 'r')
        sensitive_functions = sensitivity_file.readlines()
        sensitive_functions = [line.rstrip('\n') for line in sensitive_functions]

        #now we proceed to compute the sensitivity levels for each of the functions in the application
        sensitivity_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name), "function_sensitivity_levels.pkl")
        os.system("touch " + sensitivity_file_path)

        #if the sensitivity levels of each of the functions in the application have been computed before,
        #we just read the file, else we proceed to compute the sensitivity level
        with open(sensitivity_file_path, 'rb') as afile:
            if os.path.getsize(sensitivity_file_path) != 0:
                functions_sensitivity_levels = pickle.load(afile)
                afile.close()
            else:
                functions_sensitivity_levels = {}

        if len(functions_sensitivity_levels.items()) == 0:
            print("Getting sensitive functions...")
            functions_sensitivity_levels = self.qi.get_all_functions_sensitivity_levels(sensitive_functions)
            afile = open(sensitivity_file_path, 'wb')
            pickle.dump(functions_sensitivity_levels, afile)
            afile.close()

        self.identifier_occurrences = identifier_occurrences
        self.function_sensitivity_levels = functions_sensitivity_levels

        return [identifier_occurrences, functions_sensitivity_levels]

    def print(self, exploit_subgraph):
        print("Exploit Sub Graph")
        for node in exploit_subgraph:
            lineno = node.properties['lineno']
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, node.properties['id'])
            print(filename[0] + " " + str(lineno))

    def print_to_file(self, scores, exploit_subgraph):
        print("Scores printed in sorted_selection_scores.txt")
        sorted_selection_scores_file = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                                    "sorted_selection_scores.txt")
        os.system("touch " + sorted_selection_scores_file)
        file = open(sorted_selection_scores_file, "w")
        for key, value in scores.items():
            lineno = key.properties["lineno"]
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, key.properties['id'])
                function_name = session.write_transaction(get_function_name, key)
            print("score: " + " " + str(value) + " " + str(filename[0]) + " " + str(lineno) + " func name: " + str(
                function_name))
            file.write("score: " + " " + str(value) + " " + str(filename[0]) + " " + str(
                lineno) + " func name: " + str(function_name) + "\n")

        print("Exploit subgraph printed in exploit_subgraph.txt")

        exploit_subgraph_file = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                             "exploit_subgraph.txt")
        os.system("touch " + exploit_subgraph_file)
        file = open(exploit_subgraph_file, "w")
        for node in exploit_subgraph:
            lineno = node.properties['lineno']
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, node.properties['id'])
                function_name = session.write_transaction(get_function_name, node)
            print(filename[0] + " " + str(lineno) + " func name: " + str(function_name))
            file.write(filename[0] + " " + str(lineno) + " func name: " + str(function_name) + "\n")

    def print_reusability_to_file(self, reusability):
        print("Reusability list size: " + str(len(reusability)))
        reusability_score_file = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                              "reusability_score.txt")
        os.system("touch " + reusability_score_file)
        file = open(reusability_score_file, "w")
        for key, value in reusability.items():
            lineno = key.properties["lineno"]
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, key.properties['id'])
                function_name = session.write_transaction(get_function_name, key)
            print("score: " + " " + str(value) + " " + filename[0] + " " + str(
                lineno) + " func name: " + str(function_name) + " " + "type: " + str(key.properties["type"]))
            file.write("score: " + " " + str(value) + " " + filename[0] + " " + str(
                lineno) + " func name: " + str(function_name) + " " + "type: " + str(key.properties["type"]) + "\n")

    def print_sensitivity_to_file(self, sensitivity):
        print("Sensitivity list size: " + str(len(sensitivity)))
        sensitivity_score_file = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                              "sensitivity_scores.txt")
        os.system("touch " + sensitivity_score_file)
        file = open(sensitivity_score_file, "w")
        for key, value in sensitivity.items():
            lineno = key.properties["lineno"]
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, key.properties['id'])
                function_name = session.write_transaction(get_function_name, key)
            print("score: " + " " + str(value) + " " + filename[0] + " " + str(
                lineno) + " func name: " + str(function_name) + " " + "type: " + str(key.properties["type"]))
            file.write("score: " + " " + str(value) + " " + filename[0] + " " + str(
                lineno) + " func name: " + str(function_name) + " " + "type: " + str(key.properties["type"]) + "\n")

    def test(self):
        with self.driver.session() as session:
            results = session.write_transaction(test)[0]
            counters = {}
            for result in results:
                if result in counters:
                    counters[result] += 1
                else:
                    counters[result] = 1
            for counter in counters:
                print(counter + ": " + str(counters[counter]))

    def test1(self):
        with self.driver.session() as session:
            results = session.write_transaction(test1)[0]
            counters = {}
            for result in results:
                if result in counters:
                    counters[result] += 1
                else:
                    counters[result] = 1
            for counter in counters:
                print(counter + ": " + str(counters[counter]))

    def combine_scores(self, reusability_scores, sensitivity_scores, exploit_subgraph):
        selection_scores = {}
        tracker = {}
        sensitive_tracker = {}
        for key in reusability_scores.keys():
            key_id = key.properties["id"]
            for key1 in sensitivity_scores.keys():
                if key1.properties["id"] == key_id:
                    selection_scores[key] = reusability_scores[key] * sensitivity_scores[key1]
                    tracker[(key, (reusability_scores[key], sensitivity_scores[key1]))] = reusability_scores[key] * sensitivity_scores[key1]
                    break

        sorted_tracker = dict(sorted(tracker.items(), key=lambda x: x[1], reverse=True))
        sorted_selection_scores = dict(sorted(selection_scores.items(), key=lambda x: x[1], reverse=True))
        self.print_to_file(sorted_selection_scores, exploit_subgraph)

        print(len(sorted_selection_scores), len(sorted_tracker))
        return sorted_selection_scores, sorted_tracker

    def run_analysis(self):

        #Before we can begin computing the similarity and paths, we need to compute the similarity levels
        #for all the functions in the given application
        self.preprocess()
        # exit()
        exploit_strings_file = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                            "exploit_strings.txt")

        #Now we need to obtain the dataflow of the executed vulnerability
        dataflow_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name), "dataflow.pkl")
        os.system("touch " + dataflow_file_path)
        with open(dataflow_file_path, 'rb') as afile:
            if os.path.getsize(dataflow_file_path) != 0: #if this application is not being processed for the first time
                dataflow = pickle.load(afile)
                afile.close()
            else:
                afile.close()
                afile = open(dataflow_file_path, 'wb')
                dataflow = self.extract_dataflow_from_xdebug_trace(target_file, exploit_strings_file)  # extract dataflow subsequence Ds.
                pickle.dump(dataflow, afile)
                afile.close()

        print("Done obtaining the dataflow...")

        #Now we need to build the complete subgraph
        exploit_subgraph = self.get_exploit_subgraph(dataflow)
        self.print(exploit_subgraph)

        print("Done printing")


        reusability_scores_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                                    "reusability_scores.pkl")
        os.system("touch " + reusability_scores_file_path)

        with open(reusability_scores_file_path, 'rb') as afile:
            if os.path.getsize(reusability_scores_file_path) != 0:
                reusability_scores = pickle.load(afile)
                afile.close()
            else:
                afile.close()
                afile = open(reusability_scores_file_path, 'wb')
                reusability_scores = self.get_reusability_scores(exploit_subgraph)
                print("The rs scores are: ", reusability_scores)

                pickle.dump(reusability_scores, afile)
                afile.close()

        sensitivity_scores_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                                    "sensitivity_scores.pkl")
        os.system("touch " + sensitivity_scores_file_path)

        with open(sensitivity_scores_file_path, 'rb') as afile:
            if os.path.getsize(sensitivity_scores_file_path) != 0:
                sensitivity_scores = pickle.load(afile)
                afile.close()
            else:
                afile.close()
                afile = open(sensitivity_scores_file_path, 'wb')
                sensitivity_scores = self.get_sensitivity_scores(exploit_subgraph)
                pickle.dump(sensitivity_scores, afile)
                afile.close()

        sorted_scores, sorted_tracker = self.combine_scores(reusability_scores, sensitivity_scores, exploit_subgraph)

        self.print_debug1(reusability_scores, sensitivity_scores)
        self.print_reusability_to_file(reusability_scores)
        self.print_sensitivity_to_file(sensitivity_scores)

        ######################## BEGIN CODE TO COMPUTE SIMILAR COMPONENTS ########################

        print('starting')
        print(sorted_scores)
        print('ending')

        temp_keys = list(sorted_scores.keys())
        temp_tracker_keys = list(sorted_tracker.keys())

        temp_values = list(sorted_scores.values())
        temp_tracker_values = list(sorted_tracker.values())

        temp_dict = {}
        temp_dict2 = {}
        temp_dict[temp_keys[0]] = temp_values[0]
        temp_dict[temp_keys[1]] = temp_values[1]
        temp_dict[temp_keys[2]] = temp_values[2]
        # temp_dict[temp_keys[3]] = temp_values[3]
        # temp_dict[temp_keys[4]] = temp_values[4]
        # temp_dict[temp_keys[5]] = temp_values[5]
        # temp_dict[temp_keys[6]] = temp_values[6]
        # temp_dict[temp_keys[7]] = temp_values[7]
        # temp_dict[temp_keys[8]] = temp_values[8]

        temp_dict2[temp_tracker_keys[0]] = temp_tracker_values[0]
        temp_dict2[temp_tracker_keys[1]] = temp_tracker_values[1]
        temp_dict2[temp_tracker_keys[2]] = temp_tracker_values[2]
        # temp_dict2[temp_tracker_keys[3]] = temp_tracker_values[3]
        # temp_dict2[temp_tracker_keys[4]] = temp_tracker_values[4]
        # temp_dict2[temp_tracker_keys[5]] = temp_tracker_values[5]
        # temp_dict2[temp_tracker_keys[6]] = temp_tracker_values[6]
        # temp_dict2[temp_tracker_keys[7]] = temp_tracker_values[7]
        # temp_dict2[temp_tracker_keys[8]] = temp_tracker_values[8]

        sorted_scores = temp_dict
        sorted_tracker2 = temp_dict2

        scores = open("/opt/project/results/"+globals.application_name+"/score_details.txt", "a")
        for k, v in sorted_scores.items():
            scores.write(str(v) + "\n")

        scores.write("\n")

        for k, v in sorted_tracker2.items():
            scores.write(str(k) + "\n")


        sPathMapper = {}
        dPathMapper = {}
        total_sPaths = 0
        total_dPaths = 0
        total_exploitable_paths = 0
        total_simNodes = 0
        seed_count = 0
        node_details = {}
        sim_nodes = []
        sim_nodes_bow = []

        seeds = []
        ancestors = {}
        descendants = {}

        seed_sim_node = {}
        print("keys are: ", sorted_scores)
        for nde, score in sorted_scores.items():
            print("seeds are: ", nde.properties['lineno'], nde.properties['fileid'])
            seeds.append((nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid'])))
            seed_count += 1
            ancestorNodes = qi.run_cypher_query(get_ancestor_nodes, nde.properties['fileid'],
                                                nde.properties['lineno'])  # all parent nodes above seed n

            if ancestorNodes is None:
                print("Running sub query now ...")
                i_tracker = False
                for i in range(1, 1000):
                    ancestorNodes = qi.run_cypher_query(get_ancestor_nodes_individually, nde.properties['fileid'],
                                                 nde.properties['lineno'], i)
                    if ancestorNodes is None:
                        break
                    if ancestorNodes is not None and type(ancestorNodes) == list:
                        if (nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid'])) in ancestors:
                            for ances in ancestorNodes:
                            #     get_comp = self.get_component(ances, 'no_check')
                                ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(ances)
                        else:
                            ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))] = []
                            for ances in ancestorNodes:
                            #     get_comp = self.get_component(ances, 'no_check')
                                ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(ances)

            else:
                if ancestorNodes is not None and type(ancestorNodes) == list:
                    if (nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid'])) in ancestors:
                        for ances in ancestorNodes:
                            ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(ances)
                    else:
                        ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))] = []
                        for ances in ancestorNodes:
                            ancestors[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(ances)



            descendantNodes = qi.run_cypher_query(get_descendant_nodes, nde.properties['fileid'],
                                                  nde.properties['lineno'])  # all child nodes below seed n
            if descendantNodes is None:
                print("Running sub query now ...")
                i_tracker = False
                for i in range(1, 1000):
                    descendantNodes = qi.run_cypher_query(get_descendant_nodes_individually, nde.properties['fileid'],
                                                        nde.properties['lineno'], i)
                    if descendantNodes is None:
                        break
                    if descendantNodes is not None and type(descendantNodes) == list:
                        if (nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid'])) in descendants:
                            for des in descendantNodes:
                                descendants[(nde.properties['id'],(nde.properties['lineno'], nde.properties['fileid']))].append(des)
                        else:
                            descendants[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))] = []
                            for des in descendantNodes:
                                descendants[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(des)
            else:
                if (nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid'])) in descendants:
                    for des in descendantNodes:
                        descendants[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(des)
                else:
                    descendants[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))] = []
                    for des in descendantNodes:
                        descendants[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))].append(des)


            print("Finding similar nodes now...")
            sim_nodes_temp = self.find_similar_instruction_nodes(nde)
            sim_nodes_temp = list(sim_nodes_temp.keys())
            seed_sim_node[(nde.properties['id'], (nde.properties['lineno'], nde.properties['fileid']))] = sim_nodes_temp
            for node in sim_nodes_temp:
                if node not in sim_nodes:
                    sim_nodes.append(node)

            print("The number of sim nodes found are: ", len(sim_nodes))


            # #Alternate comparison method
            #
            # sim_nodes_temp_bag_of_words_method = self.find_sim_instructions_bows(nde)
            # sim_nodes_temp_bow = list(sim_nodes_temp_bag_of_words_method.keys())
            # for node in sim_nodes_temp_bow:
            #     if node not in sim_nodes_bow:
            #         sim_nodes_bow.append(node)
            #
            # print("The number of sim nodes found through bow method are:", len(sim_nodes_bow))

        print("End of part 1")

        ####################################################################################################

        # sim_nodes_file = open("/opt/project/results/dailyexpensetrackerproject/sim_details.txt", "r")
        # sim_nodes = []
        # all_nodes = sim_nodes_file.readlines()
        # for each_node in all_nodes:
        #     list_of_node = each_node.split()
        #     sim_nodes.append((int(list_of_node[2]), int(list_of_node[3])))
        #
        path_details = open("/opt/project/results/codeastro/path_details.txt", "a")
        all_sources = qi.run_cypher_query(get_all_sources)
        all_sinks = qi.run_cypher_query(get_all_sinks)

        avg_sim_comp_d = 0
        avg_sim_comp = 0
        print("Part 1 done...")
        source_number = 0
        B = {}
        F = {}
        component_tracker = {}
        source_file_tracker = {}
        atleast_one_tracker = {}
        atleast_one_path = []

        for node in sim_nodes:  # for each of those instructions
            for each_source in all_sources:
                path_present = None
                path_present_specific = None
                source_number += 1
                print("running 2..", each_source, "&", node, "source number:", source_number, "simnodes",
                      len(sim_nodes))
                sPaths = 0
                if each_source[1] != node[1]:
                    if node[1] in atleast_one_tracker and atleast_one_tracker[node[1]] == "moveon":
                        continue
                    else:
                        atleast_one_path = qi.run_cypher_query(at_least_one_path, node[1]) #atleast one flows_to present to that file from a different file
                else:
                    atleast_one_path = [1]
                if atleast_one_path == []: #no path exists to that file from a different file
                    atleast_one_tracker[node[1]] = "moveon"
                    continue
                else:
                    if (each_source[1], (node[0], node[1])) in source_file_tracker and source_file_tracker[(each_source[1], (node[0], node[1]))] == "Nope":
                        continue
                        #first individually check for paths between source and sim node
                    path_present_specific = qi.run_cypher_query(get_paths_count_source_file_specific, each_source[0],
                                                                each_source[1], node[0], node[1])
                    if path_present_specific == 0:
                        continue #if no paths are present, then move on
                    if path_present_specific is None: #if query crashes, then check if there are any paths from any of the source nodes in that file, to that sim node
                        if (each_source[1], (node[0], node[1])) in source_file_tracker:
                            path_present = source_file_tracker[(each_source[1], (node[0], node[1]))]
                        else:
                            path_present = qi.run_cypher_query(get_paths_count_source_file, each_source[1], node[0], node[1])
                            if path_present == 0: #proves there are no paths from any of the source nodes to the sim node
                                source_file_tracker[(each_source[1], (node[0], node[1]))] = "Nope"
                                continue
                            elif path_present == None: #query has crashed, so we need to check the sub queries
                                path_present_specific = "sub"
                            else:
                                source_file_tracker[(each_source[1], (node[0], node[1]))] = "Yep"

                    if path_present_specific is not None or path_present != "Nope":

                        if path_present_specific != "sub":
                            sPaths = qi.run_cypher_query(get_paths_from_source_to_node, each_source[0], each_source[1], node[0],
                                                         node[1])  # cfg paths
                        else:
                            sPaths = None

                        if sPaths == None:  # most likely query timeout
                            print("Running sub query now ...")
                            i_tracker = False
                            for i in range(1, 1000):
                                print("i value is: ", i)
                                sPaths = qi.run_cypher_query(get_paths_from_source_to_node_individually, each_source[0],
                                                             each_source[1], node[0], node[1], i)
                                if sPaths is None:
                                    break
                                if sPaths is not None and type(sPaths) == list:
                                    for path in sPaths:
                                        for n in seed_sim_node:
                                            if node in seed_sim_node[n]:
                                                sim_nodes_counter = 0
                                                total_nodes_counter = 0
                                                anc = ancestors[n]
                                                for x in range(0, len(path.nodes)):
                                                    for nd in anc:
                                                        if ((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2])) in component_tracker:
                                                            sim_o_not = component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))]
                                                        else:
                                                            sim_o_not= self.find_sim_nodes_2(path.nodes[x], (nd[1], nd[2]))
                                                            component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))] = sim_o_not

                                                        if sim_o_not == "sim":
                                                            sim_nodes_counter += 1
                                                            break
                                                    total_nodes_counter += 1

                                                B[(path, ((each_source[0], each_source[1]), (node[0], node[1])))] = sim_nodes_counter/total_nodes_counter

                        elif sPaths is not None and type(sPaths) == list:
                            for path in sPaths:
                                for n in seed_sim_node:
                                    if node in seed_sim_node[n]:
                                        sim_nodes_counter = 0
                                        total_nodes_counter = 0
                                        anc = ancestors[n]
                                        for x in range(0, len(path.nodes)):
                                            for nd in anc:
                                                if ((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2])) in component_tracker:
                                                    sim_o_not = component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))]
                                                else:
                                                    sim_o_not= self.find_sim_nodes_2(path.nodes[x], (nd[1], nd[2]))

                                                    component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))] = sim_o_not
                                                if sim_o_not == "sim":
                                                    sim_nodes_counter += 1
                                                    break
                                            total_nodes_counter += 1
                                        B[(path, ((each_source[0], each_source[1]), (node[0], node[1])))] = sim_nodes_counter/total_nodes_counter

        if len(B) > 0:
            output = dict(sorted(B.items(), key=lambda item: item[1], reverse=True))
            B = output
            cutoff = 75/100 * len(B)
            comp = list(B.values())
            sim_comp_count = []
            for i in range(0, len(B)):
                if i < cutoff:
                    total_sPaths += 1
                    sim_comp_count.append(comp[i])
                else:
                    break
            if len(sim_comp_count) > 0:
                avg_sim_comp = (sum(sim_comp_count)/len(sim_comp_count))*100

        print("the avg sim count is: ", avg_sim_comp)
        print("spaths are:", total_sPaths)

        #################################

        all_sinks = qi.run_cypher_query(get_all_sinks)
        each_sink = 0
        sink_file_tracker = {}
        atleast_one_tracker = {}
        for node in sim_nodes:  # for each of those instructions
            for each_source in all_sinks:
                dPaths = 0
                each_sink += 1
                print("running 3..", each_source, "and", node, "sink number:", each_sink, "simnodes",
                      len(sim_nodes))
                path_present_specific = None
                path_present = None
                if each_source[1] != node[1]:
                    if each_source[1] in atleast_one_tracker and atleast_one_tracker[each_source[1]] == "moveon":
                        continue
                    else:
                        atleast_one_path = qi.run_cypher_query(at_least_one_path, each_source[1]) #atleast one flows_to present to that file from a different file
                else:
                    atleast_one_path = [1]
                if atleast_one_path == []: #no path exists to that file from a different file
                    atleast_one_tracker[each_source[1]] = "moveon"
                    continue
                else:
                    if (each_source[1], (node[0], node[1])) in sink_file_tracker and sink_file_tracker[(each_source[1], (node[0], node[1]))] == "Nope":
                        continue
                    path_present_specific = qi.run_cypher_query(get_paths_count_sink_file_specific, each_source[0],
                                                                each_source[1], node[0], node[1])
                    if path_present_specific == 0:
                        continue
                    if path_present_specific is None:
                        if (each_source[1], (node[0], node[1])) in sink_file_tracker:
                            path_present = sink_file_tracker[(each_source[1], (node[0], node[1]))]
                        else:
                            path_present = qi.run_cypher_query(get_paths_count_sink_file, each_source[1], node[0], node[1])
                            if path_present == 0:
                                sink_file_tracker[(each_source[1], (node[0], node[1]))] = "Nope"
                                continue
                            elif path_present == None: #query has crashed, so we need to check the sub queries
                                path_present_specific = "sub"
                            else:
                                sink_file_tracker[(each_source[1], (node[0], node[1]))] = "Yep"

                    if path_present_specific is not None or path_present != "Nope":

                        if path_present_specific != "sub":
                            dPaths = qi.run_cypher_query(get_paths_from_node_to_sink, each_source[0], each_source[1], node[0],
                                                             node[1])  # cfg paths
                        else:
                            dPaths = None

                        if dPaths is None:  # most likely query timedout
                            print("Running sub query now ...")
                            i_tracker = False
                            for i in range(1, 1000):
                                print("I in this case is:", i)
                                dPaths = qi.run_cypher_query(get_paths_from_node_to_sink_individually, each_source[0],
                                                             each_source[1], node[0], node[1], i)
                                if dPaths is None:
                                    break
                                if dPaths is not None and type(dPaths) == list:
                                    for path in dPaths:
                                        for n in seed_sim_node:
                                            if node in seed_sim_node[n]:
                                                sim_nodes_counter = 0
                                                total_nodes_counter = 0
                                                des = descendants[n]
                                                for x in range(0, len(path.nodes)):
                                                    for nd in des:
                                                        if ((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2])) in component_tracker:
                                                            sim_o_not = component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))]
                                                        else:
                                                            sim_o_not  = self.find_sim_nodes_2(path.nodes[x], (nd[1], nd[2]))
                                                            component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))] = sim_o_not
                                                        if sim_o_not == "sim":
                                                            sim_nodes_counter += 1
                                                            break
                                                    total_nodes_counter += 1

                                                F[(path, ((each_source[0], each_source[1]), (node[0], node[1])))] = sim_nodes_counter/total_nodes_counter


                        elif dPaths is not None and type(dPaths) == list:

                            for path in dPaths:
                                for n in seed_sim_node:
                                    if node in seed_sim_node[n]:
                                        sim_nodes_counter = 0
                                        total_nodes_counter = 0
                                        des = descendants[n]
                                        for x in range(0, len(path.nodes)):
                                            for nd in des:
                                                if ((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2])) in component_tracker:
                                                    sim_o_not = component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))]
                                                else:
                                                    sim_o_not= self.find_sim_nodes_2(path.nodes[x], (nd[1], nd[2]))
                                                    component_tracker[((path.nodes[x]['lineno'], path.nodes[x]['fileid']), (nd[1], nd[2]))] = sim_o_not
                                                if sim_o_not == "sim":
                                                    sim_nodes_counter += 1
                                                    break
                                            total_nodes_counter += 1

                                        F[(path, ((each_source[0], each_source[1]), (node[0], node[1])))] = sim_nodes_counter/total_nodes_counter



        if len(F) > 0:
            output = dict(sorted(F.items(), key=lambda item: item[1], reverse=True))
            F = output
            cutoff = 75/100 * len(F)
            comp = list(F.values())
            sim_comp_count = []
            for i in range(0, len(F)):
                if i < cutoff:
                    total_dPaths += 1
                    sim_comp_count.append(comp[i])

                else:
                    break
            if len(sim_comp_count) > 0:
                avg_sim_comp_d = (sum(sim_comp_count) / len(sim_comp_count))*100
        print("Done...")
        print("The total dpaths are: ", total_dPaths, " and the total spaths are:", total_sPaths)
        print("The average sim count is: ", avg_sim_comp, avg_sim_comp_d)

        fileid_name_dict = {}
        fileids_filenames = qi.run_cypher_query(fileid_to_filename)
        for each_pair in fileids_filenames:
            fileid_name_dict[each_pair[0]] = each_pair[1]

        sim_file = open("/opt/project/results/codeastro/s_exp_paths.txt", "w")
        sim_file2 = open("/opt/project/results/codeastro/d_exp_paths.txt", "w")
        print("Now to count the number of sat paths...")
        cutoff = 75 / 100 * len(B)
        exp_paths_count_s = 0
        cut_off_counter = 0
        actual_exp_paths = []


        for each_path in B:
            print("Cut off is", cutoff, "we are at", cut_off_counter)
            if cut_off_counter > cutoff:
                break
            cut_off_counter += 1
            nodes = each_path[1]
            source_details = nodes[0]
            node_details = nodes[1]
            print(source_details, node_details)
            checker = qi.run_cypher_query(check_reaches, source_details[0], source_details[1], node_details[0], node_details[1])
            if type(checker) == int and checker > 0:
                exp_paths_count_s += 1
                the_paths = qi.run_cypher_query(get_check_reaches, source_details[0], source_details[1], node_details[0], node_details[1])
                for each_path in the_paths:
                    temp_list = []
                    for x in range(0, len(each_path.nodes)):
                        temp_list.append((each_path.nodes[x]['lineno'], fileid_name_dict[each_path.nodes[x]['fileid']]))
                    actual_exp_paths.append(temp_list)

        for exp_path in actual_exp_paths:
            sim_file.write(str(exp_path) + "\n")

        cutoff = 75 / 100 * len(F)
        exp_paths_count_d = 0
        cut_off_counter = 0
        actual_exp_paths2 = []
        for each_path in F:
            print("Cut off 2 is", cutoff, "we are at", cut_off_counter)
            if cut_off_counter > cutoff:
                break
            cut_off_counter += 1
            nodes = each_path[1]
            node_details = nodes[1]
            sink_details = nodes[0]
            checker = qi.run_cypher_query(check_reaches2, node_details[0], node_details[1], sink_details[0], sink_details[1])
            if type(checker) == int and checker > 0:
                exp_paths_count_d += 1
                the_paths = qi.run_cypher_query(get_check_reaches2, node_details[0], node_details[1], sink_details[0], sink_details[1])
                for each_path in the_paths:
                    temp_list = []
                    for x in range(0, len(each_path.nodes)):
                        temp_list.append((each_path.nodes[x]['lineno'], fileid_name_dict[each_path.nodes[x]['fileid']]))
                    actual_exp_paths2.append(temp_list)

        for exp_path in actual_exp_paths2:
            sim_file2.write(str(exp_path) + "\n")


        print("Done...")
        print("The total dpaths are: ", total_dPaths, " and the total spaths are:", total_sPaths)
        print("The average sim count is: ", avg_sim_comp, avg_sim_comp_d)
        print("The number of exp paths count s and d are: ", exp_paths_count_s, exp_paths_count_d)
        exit() #done


    def find_sim_nodes_2(self, spath_node, ancestor_node):
        if spath_node['lineno'] is None or ancestor_node[0] is None:
            return "no sim"
        mod_checker = 0
        no_sim = True

        #obtain all the nodes of the subtree
        spath_root = ''
        spath_node_child = ''
        if (spath_node['lineno'], spath_node['fileid']) in node_details2:
            spath_root = node_details2[(spath_node['lineno'], spath_node['fileid'])][0]
        else:
            spath_nodes = qi.run_cypher_query(get_short_subtree, spath_node['lineno'], spath_node['fileid'])
            ancestor_node_child = ''
            spath_node_child = ''

            #find the parent nodes
            for each_node in spath_nodes:
                if each_node['type'] == 'AST_TOPLEVEL':
                    continue
                checker_parent = qi.run_cypher_query(check_parent, each_node)
                if checker_parent['lineno'] != each_node['lineno']:
                    spath_root = each_node
                    break
        #obtain the child nodes
        if spath_root != '':
            if (spath_node['lineno'], spath_node['fileid']) in node_details2:
                spath_node_child = node_details2[(spath_node['lineno'], spath_node['fileid'])][1]
            else:
                spath_node_child = qi.run_cypher_query(get_short_child, spath_root)
                node_details2[(spath_node['lineno'], spath_node['fileid'])] = (spath_root, spath_node_child)


        ancestor_root = ''
        ancestor_node_child = ''
        if (ancestor_node[0], ancestor_node[1]) in node_details2:
            ancestor_root = node_details2[(ancestor_node[0], ancestor_node[1])][0]
        else:
            ancestor_nodes = qi.run_cypher_query(get_short_subtree, ancestor_node[0], ancestor_node[1])

            for each_node in ancestor_nodes:
                if each_node['type'] == 'AST_TOPLEVEL':
                    continue
                checker_parent = qi.run_cypher_query(check_parent, each_node)
                if checker_parent['lineno'] != each_node['lineno']:
                    ancestor_root = each_node
                    break
        if ancestor_root != '':
            if (ancestor_node[0], ancestor_node[1]) in node_details2:
                ancestor_node_child = node_details2[(ancestor_node[0], ancestor_node[1])][1]
            else:
                ancestor_node_child = qi.run_cypher_query(get_short_child, ancestor_root)
                node_details2[(ancestor_node[0], ancestor_node[1])] = (ancestor_root, ancestor_node_child)

        if spath_node_child != '' and ancestor_node_child != '' and \
            spath_node_child != None and ancestor_node_child != None:
            if len(spath_node_child) == len(ancestor_node_child):  # make sure the lengths are the same
                for x in range(0, len(spath_node_child)):
                    if spath_node_child[x]['type'] == ancestor_node_child[x]['type']:
                        if spath_node_child[x]['type'] == 'string' and \
                                ancestor_node_child[x]['type'] == 'string' and \
                                spath_node_child[x]['code'] == ancestor_node_child[x]['code']:
                            continue
                        elif spath_node_child[x]['type'] == 'string' and \
                                ancestor_node_child[x]['type'] == 'string' and \
                                spath_node_child[x]['code'] != ancestor_node_child[x]['code']:
                            mod_checker += 1
                    else:
                        no_sim = False
                        break
                if no_sim and mod_checker <= 1:
                    return "sim"
            else:
                return "no sim"


    def find_similar_instruction_nodes(self, n):
        simNodes = {}
        file_lineno = n.properties['lineno']
        file_id = n.properties['fileid']
        # file_name = qi.run_cypher_query(get_filename_from_fileid, file_id)
        # file = open(file_name)
        # content = file.readlines()
        # instruction = content[file_lineno]
        main_instr = []
        file_items_list = []
        with open("/opt/project/intermediate_results/" + globals.application_name + "/nodes.csv", 'r',
                  errors='ignore') as nodes_file:
            # heading = next(nodes_file)
            reader_obj = csv.reader((row.replace('\0', '') for row in nodes_file), delimiter='\t')
            for row88 in reader_obj:
                file_items_list.append(row88)

        main_instr = []
        for itmms in file_items_list:
            if len(itmms) < 14 and len(itmms) > 8 and itmms[4] != '' and itmms[7] != '' and \
                    int(itmms[4]) == file_lineno and int(itmms[7]) == file_id:

                if itmms[2] == "string":
                    if '<' not in itmms[5] and '>' not in itmms[5] and '/' not in itmms[5] and '\\' not in itmms[5]:
                        main_instr.append(itmms[2])
                        main_instr.append(itmms[5])
                else:
                    main_instr.append(itmms[2])


        other_instrs = {}
        for itmms in file_items_list:
            if len(itmms) < 14 and len(itmms) > 8 and itmms[4] != '' and itmms[7] != '' and \
                    int(itmms[4]) != file_lineno and int(itmms[7]) != file_id:
                if itmms[2] == "string":
                    if '<' not in itmms[5] and '>' not in itmms[5] and '/' not in itmms[5] and '\\' not in itmms[5]:
                        if (int(itmms[4]), int(itmms[7])) in other_instrs:
                            other_instrs[(int(itmms[4]), int(itmms[7]))].append(itmms[2])
                            other_instrs[(int(itmms[4]), int(itmms[7]))].append(itmms[5])
                        else:
                            other_instrs[(int(itmms[4]), int(itmms[7]))] = [itmms[2], itmms[5]]
                else:
                    if (int(itmms[4]), int(itmms[7])) in other_instrs:
                        other_instrs[(int(itmms[4]), int(itmms[7]))].append(itmms[2])
                    else:
                        other_instrs[(int(itmms[4]), int(itmms[7]))] = [itmms[2]]

        for every_instr in other_instrs:
            sim_check = 0
            if len(other_instrs[every_instr]) == len(main_instr):
                for i in range(0, len(other_instrs[every_instr])):
                    if other_instrs[every_instr][i] != main_instr[i]:
                        sim_check += 1
                if sim_check <= 1 and every_instr not in simNodes:
                    simNodes[every_instr] = "sim"


        return simNodes

    def find_similar_nodes(self, n, mod, sorted_scores, node_details):
        print("the n node is: ", n.properties)
        simNodes = {}
        sim_count = 0
        main_instruction_subtree_nodes = qi.run_cypher_query(get_short_subtree, n.properties['lineno'], n.properties['fileid'])
        root_node = ''
        for each_node in main_instruction_subtree_nodes:
            checker_parent = qi.run_cypher_query(check_parent, each_node)
            if checker_parent['lineno'] != each_node['lineno']:
                root_node = each_node
                break
        child_nodes = qi.run_cypher_query(get_short_child, root_node)

        other_instruction_locations = qi.run_cypher_query(get_other_location, root_node)
        for every_location in other_instruction_locations:
            sim_count += 1
            print("At count:", sim_count, "total: ", len(other_instruction_locations))
            no_sim = True
            mod_checker = 0
            other_root_node = ''
            if (every_location[0], every_location[1]) in node_details:
                other_root_node = node_details[(every_location[0], every_location[1])][0]
            else:
                subtree_nodes = qi.run_cypher_query(get_short_subtree, every_location[0], every_location[1])
                for each_node in subtree_nodes:
                    # if each_node['type'] == "AST_ECHO" or each_node['is_source'] == True: #we don't want sim nodes that are sources/sinks
                    #     break
                    if each_node['type'] == 'AST_TOPLEVEL':
                        continue
                    checker_parent = qi.run_cypher_query(check_parent, each_node)
                    if checker_parent['lineno'] != each_node['lineno']:
                        other_root_node = each_node
                        break
            if other_root_node != '':
                if (every_location[0], every_location[1]) in node_details:
                    other_child_nodes = node_details[(every_location[0], every_location[1])][1]
                else:
                    other_child_nodes = qi.run_cypher_query(get_short_child, other_root_node)
                    node_details[(every_location[0], every_location[1])] = (other_root_node, other_child_nodes)
                if len(child_nodes) == len(other_child_nodes):
                    for x in range(0, len(other_child_nodes)):
                        if other_child_nodes[x]['type'] == child_nodes[x]['type']:
                            if other_child_nodes[x]['type'] == 'string' and child_nodes[x]['type'] == 'string' and \
                                    other_child_nodes[x]['code'] == child_nodes[x]['code']:
                                continue
                            elif other_child_nodes[x]['type'] == 'string' and child_nodes[x]['type'] == 'string' and \
                                other_child_nodes[x]['code'] != child_nodes[x]['code']:
                                mod_checker += 1
                        else: #if types dont match, we say no similarity exist
                            no_sim = False
                            break
                    if no_sim and mod_checker <= 1:
                        if (other_root_node['lineno'], other_root_node['fileid']) not in simNodes:
                            simNodes[(other_root_node['lineno'], other_root_node['fileid'])] = "similar"
                            sim_details.write(str(other_root_node['lineno']) + ", " + str(other_root_node['fileid']) + "\n")

        return simNodes, node_details

    def get_reusability_scores(self, exploit_subgraph):
        reusability_scores = {}
        for node in exploit_subgraph:
            if node is not None:
                nodes = self.get_subtree(node)
                calls_in_node = self.get_calls(nodes)
                methods_in_node = self.get_methods(nodes)
                variables_in_node = self.get_variables(nodes)
                superglobals_in_node = self.get_superglobals(nodes)
                reusability_scores[node] = self.count_occurrences(calls_in_node, methods_in_node, variables_in_node,
                                                                  superglobals_in_node)
        return reusability_scores

    def get_component(self, node, check):
        if check == 'count':
            result = []
            list = ["_GET", "GET", "_POST", "POST", "_SERVER", "SERVER", "_REQUEST", "REQUEST", "_FILES", "FILES",
                    "_SESSION", "SESSION", "_COOKIE", "COOKIE"]
            if node is not None:
                nodes = qi.run_cypher_query(get_short_subtree, node)
                if nodes is not None:
                    for n in nodes:
                        if n['type'] == "AST_VAR":
                            result.append('variables')
                        if n['type'] == 'string':
                            if n["code"] in list:
                                result.append('superglobals')
                        if node['type'] == "AST_CALL":
                            result.append('calls')
                        if node['type'] == "AST_METHOD_CALL":
                            result.append('methods')
            return result
        else:
            result = []
            list = ["_GET", "GET", "_POST", "POST", "_SERVER", "SERVER", "_REQUEST", "REQUEST", "_FILES", "FILES",
                    "_SESSION", "SESSION", "_COOKIE", "COOKIE"]
            if node is not None:
                nodes = qi.run_cypher_query(get_short_subtree, node)
                if nodes is not None:
                    for n in nodes:
                        if n['type'] == "AST_VAR":
                            result.append('variables')
                        if n['type'] == 'string':
                            if n["code"] in list:
                                result.append('superglobals')
                        if n['type'] == "AST_CALL":
                            result.append('calls')
                        if n['type'] == "AST_METHOD_CALL":
                            result.append('methods')
                        return result

    def get_sensitivity_scores(self, exploit_subgraph):
        sensitivity_scores = {}
        sensitive_functions_file_path = os.path.join(os.path.join(globals.RESULTS_DIR, globals.application_name),
                                                     "sensitive_functions.txt")
        sensitivity_file = open(sensitive_functions_file_path, 'r')
        sensitive_functions = sensitivity_file.readlines()
        sensitive_functions = [line.rstrip('\n') for line in sensitive_functions]

        node_count = 0
        for node in exploit_subgraph:
            node_count += 1
            print("Among the nodes for sensitivity, we are ", node_count, " out of ", len(exploit_subgraph))
            sensitivity_scores[node] = self.get_sensitivity_score(node, sensitive_functions)
        return sensitivity_scores

    def get_sensitivity_score(self, node, sensitive_functions):
        sensitivity_score = 0
        with self.driver.session() as session:
            node_identifiers = session.write_transaction(get_identifiers, node)
            for identifier in node_identifiers:
                if identifier in sensitive_functions:
                    sensitivity_score += 1

                nodes = self.get_subtree(node)
                calls = self.get_calls(nodes)
                if len(calls) > 0:
                    for call in calls:
                        method_definitions = session.write_transaction(get_callee, call)  # follow CALLS edge
                        print("Method definitions are: ", method_definitions)
                        if len(method_definitions) == 0:  # PHP native functions
                            continue
                        elif len(method_definitions) == 1:  # if CALLS edge exists and is unique

                            method = method_definitions[0]
                            if method in self.function_sensitivity_levels:
                            # method_id = method
                            # if method_id != "null":
                                score = self.function_sensitivity_levels[method]
                                sensitivity_score += score
                        else:  # more than one CALLS edges, ambiguous definition
                            s = 0
                            for method_def in method_definitions:  # get highest score
                                if method_def in self.function_sensitivity_levels:
                                    if s < self.function_sensitivity_levels[method_def]:
                                        s = self.function_sensitivity_levels[method_def]
                            sensitivity_score += s
        # a Value of 0 for the sensitivity score would nullify the value of the usability score. We are instead setting it to a very small value of 0.0001
        if sensitivity_score == 0:
            sensitivity_score = 0.0001
        return sensitivity_score

    def count_occurrences(self, calls, methods, variables, superglobals):
        reuse_occurrences = {}
        call_occurrences = self.identifier_occurrences["calls_occurrences"]  # {"call_name": 5}
        methods_occurrences = self.identifier_occurrences["methods_occurrences"]  # {"call_name": 5}
        variable_occurrences = self.identifier_occurrences["variable_occurrences"]  # {"call_name": 5}
        superglobal_occurrences = self.identifier_occurrences["superglobal_occurrences"]  # {"call_name": 5}

        for call in calls:
            if call in call_occurrences:
                reuse_occurrences[call] = ["call", call_occurrences[call]]
        for method in methods:
            if method in methods_occurrences:
                reuse_occurrences[method] = ["method", methods_occurrences[method]]
        for variable in variables:
            if variable in variable_occurrences:
                reuse_occurrences[variable] = ["variable", variable_occurrences[variable]]
        for superglobal in superglobals:
            if superglobal in superglobal_occurrences:
                reuse_occurrences[superglobal] = ["superglobal", superglobal_occurrences[superglobal]]
        # normalize
        score = self.combine_occurrences(reuse_occurrences)
        return score

    # return a single reuse score from the multiple occurrences
    def combine_occurrences(self, reuse_occurrences):
        total_sum = 0
        call_occurrences = self.identifier_occurrences["calls_occurrences"]  # {"call_name": 5}
        methods_occurrences = self.identifier_occurrences["methods_occurrences"]  # {"call_name": 5}
        variable_occurrences = self.identifier_occurrences["variable_occurrences"]  # {"call_name": 5}
        superglobal_occurrences = self.identifier_occurrences["superglobal_occurrences"]  # {"call_name": 5}
        for key, item in call_occurrences.items():
            total_sum += item
        for key, item in methods_occurrences.items():
            total_sum += item
        for key, item in variable_occurrences.items():
            total_sum += item
        for key, item in superglobal_occurrences.items():
            total_sum += item
        # formula 1: weighted sum.

        # make the change to the forumula here
        # Rs is the number of times component is present in application / total number of times all components
        calls = methods = variables = superglobals = score = 0

        for key, item in reuse_occurrences.items():
            # total_sum += item[1]
            if item[0] == "call":
                calls += item[1]
            elif item[0] == "method":
                methods += item[1]
            elif item[0] == "variable":
                variables += item[1]
            elif item[0] == "superglobal":
                superglobals += item[1]  # this is not very meaningful
        # score = calls + methods + int(variables * 0.5)
        if total_sum != 0:
            score = (calls + methods + variables + superglobals) / total_sum

        print("calls: " + str(calls))
        print("methods: " + str(methods))
        print("variables: " + str(variables))
        print("superglobals: " + str(superglobals))
        print(total_sum)
        print("score: " + str(score))
        return score

    def get_calls(self, nodes):
        calls = []
        for node in nodes:
            if node.properties['type'] == "AST_CALL":
                position = nodes.index(node)
                name = nodes[position + 2].properties["code"]
                calls.append(node)
        return calls

    def get_superglobals(self, nodes):
        superglobals = []
        list = ["_GET", "GET", "_POST", "POST", "_SERVER", "SERVER", "_REQUEST", "REQUEST", "_FILES", "FILES",
                "_SESSION", "SESSION", "_COOKIE", "COOKIE"]
        for node in nodes:
            if node.properties['type'] == 'string':
                if node.properties["code"] in list:
                    superglobals.append(node.properties["code"])
        return superglobals

    def get_methods(self, nodes):
        method_names = []
        for node in nodes:
            if node.properties['type'] == "AST_METHOD_CALL":
                with self.driver.session() as session:
                    name_node = session.write_transaction(get_method_name, node)
                    if len(name_node) > 0:
                        method_name = name_node[0] + "->" + name_node[1]
                    # object_name = session.write_transaction(get_ith_ith_children, node, 0, 1)
                    method_names.append(method_name)
        return method_names

    def get_variables(self, nodes):
        var_names = []
        for node in nodes:
            if node.properties['type'] == "AST_VAR":
                position = nodes.index(node)
                var_name = nodes[position + 1].properties["code"]
                if self.is_not_blacklisted(var_name):
                    var_names.append(var_name)
        return var_names

    def is_not_blacklisted(self, var_name):
        list = ["this", "_GET", "_POST", "_SERVER", "_REQUEST", "_FILES", "_SESSION", "_COOKIE"]
        if var_name in list:
            return False
        else:
            return True

    def get_subtree(self, node):
        with self.driver.session() as session:
            nodes = session.write_transaction(get_subtree, node)
            return nodes

    def get_exploit_subgraph(self, dataflow):
        from generate_path_adv import search_result, rec_search_cond, add_to_ddgpath
        # retrieve nodes in dataflow from CPG
        print("Done obtaining")
        DDGpath = []
        for location in dataflow:
            with self.driver.session() as session:
                node = session.write_transaction(get_node_file_line, location[0], location[1])
                if node is not None:
                    DDGpath.append(node)
        print("Outside the for loop")
        # Expand DDG path by adding conditional statements enclosing its nodes
        elem_counter = 0
        extracted_counter = 0
        try:
            queue = [{"node": node, "depth": 0} for node in DDGpath]

            for elem in queue:
                elem_counter += 1
                print("elem number ", elem_counter, "out of", len(queue))
                rec_search_cond(elem, self.qi)  # recursively add conditional statements that enclose the instruction
            for extracted_node in search_result:
                extracted_counter += 1
                print("extracted_counter ", extracted_counter, "out of", len(search_result))
                add_to_ddgpath(extracted_node.get("node"),
                               DDGpath)  # enhance the path with the conditional statement node found, if any
            search_result.clear()
        except Exception as e:
            print("Exception occurred while searching for conditional statements")
            print(str(e))
        return DDGpath

    # filename: file containing xdebug trace
    # exploit_strings: the malicious strings in input, as an array. E.g., "alert(1);" or alert%281%29 as URL encoded.
    # These should be set manually in an external file when reproducing an exploit
    def extract_dataflow_from_xdebug_trace(self, filename, exploit_strings_file):
        print("Extracting dataflow from the xdebug trace...")
        all_variables = []
        values = []
        final_values = []
        final_variables = []
        dataflow = []
        target_file = "/var/www/html/"+globals.application_name+"/admin/category/index.php"
        with open('/opt/project/results/'+globals.application_name+'/request_data.json', "r") as f:
            params = json.load(f)
        params = params["params"]
        for i in range(0, len(params)):
            all_variables.append(list(params.keys())[i])
            values.append(list(params.values())[i])

        print("Narrowing down exploitable vulnerabilities...")
        for x in range(0, len(values)):
            if 'alert' in str(values[x]):
                final_values.append(values[x])
                final_variables.append(all_variables[x])

        print("Getting seed information...")
        fileid = qi.run_cypher_query(get_fileid_from_filename, target_file)
        print("the fileid is: ", fileid, target_file)
        starting_lineno = qi.run_cypher_query(code_words_linenos, final_variables[0], fileid)
        print("the fileid and lineno is: ", fileid, starting_lineno, final_variables[0])
        temp_dict = {}
        temp_dict[(fileid, starting_lineno)] = 'not_checked'

        checker = True
        while checker == True:
            all_keys = list(temp_dict.keys())
            all_values = list(temp_dict.values())
            not_checked_counter = 0
            for n in range(0, len(all_values)):
                if all_values[n] == 'not_checked':
                    not_checked_counter += 1
            print("not checked counter is: ", not_checked_counter)

            if 'not_checked' in all_values:
                checker = True
            else:
                checker = False
            for n in range(0, len(all_keys)):
                if all_values[n] == 'checked':
                    continue
                elif all_values[n] == 'not_checked':
                    file_n_lineno_reaches = qi.run_cypher_query(file_lineno, all_keys[n][0], all_keys[n][1])
                    temp_dict[all_keys[n]] = 'checked'
                    for details in file_n_lineno_reaches:
                        if (details[0], details[1]) not in temp_dict:
                            temp_dict[(details[0], details[1])] = 'not_checked'

        file_n_lineno_reaches = list(temp_dict.keys())
        print("Getting seeds...")
        for details in file_n_lineno_reaches:
            fileid = details[0]
            lineno = details[1]
            filename = qi.run_cypher_query(get_filename_from_fileid, fileid)
            dataflow.append([filename, lineno])

        return dataflow

    def print_debug1(self, reusability, sensitivity):
        print("REUSABILITY and SENSITIVITY scores")
        print("Reusability list size: " + str(len(reusability)))
        print("Sensitivity list size: " + str(len(sensitivity)))
        shorter = {}
        longer = {}

        if len(sensitivity) <= len(reusability):
            shorter = sensitivity
            longer = reusability
        else:
            shorter = reusability
            longer = sensitivity
        print(reusability.keys())
        for key, value in shorter.items():
            key_id = key.properties["id"]
            lineno = key.properties["lineno"]
            with self.driver.session() as session:
                filename = session.write_transaction(get_filename_of_node, key_id)[0]
                print(filename + ":" + str(lineno))