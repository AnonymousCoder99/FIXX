from functools import lru_cache

# from DynamicAnalysis import DynamicAnalysis
# from DynamicAnalysis import DynamicAnalysis
import logging
import os

#logging.basicConfig(level=logging.DEBUG)
import globals

logging.getLogger("httpstream").setLevel(logging.WARNING)
SS_NAME = os.environ.get("SS_NAME","uic_1")
logger = logging.getLogger(SS_NAME)

from neo4j import GraphDatabase
from migration_neo4j_4.cypher_queries import *

uri = 'bolt://127.0.0.1:' + str(globals.NEO4J_BOLT_PORT)
user = 'neo4j'
password = 'user'
INVALID_NODEID = 83740932


#driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)


class CPGQueryInterface:
    da = None
    total_time = 0  # in Seconds

    def __init__(self, driver=None):
        #print("Connecting...")
        if not driver:
            self.driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
        else:
            self.driver = driver
        #print("Connected!")
    # def __init__(self):
    #     self.da = DynamicAnalysis(7474)

    def add_query_time(self, result_summary):
        self.total_time += (result_summary.result_available_after + result_summary.result_consumed_after)/1000.0

    def run_cypher_query(self, query_func, *args):
        # TODO: Pass arguments with names, keyword arguments
        with self.driver.session() as session:
            try:
                result = session.write_transaction(query_func, *args)
            except Exception as e:
                print(e)
                result = None
            # self.add_query_time(result_summary)
            return result

    def get_full_path(self, nodeids):
        result = self.run_cypher_query(get_full_path_from_ids, nodeids)
        return result

    def getDDGPaths(self, sinkid, sourceid):
        result = self.run_cypher_query(get_ddg_paths, sinkid, sourceid)
        paths = []
        if result:
            # We are expecting only one path, the query also limit path result to 1
            path = result[0]
            # nodes = [node.get('id') for node in path.nodes]
            # print(nodes)
            # Break down the path into multiple paths with ast_prop_ddg
            temp = []
            for rel in path.relationships:
                # print(rel.start_node.id, rel.get('type'), temp, paths)
                temp.append(rel.end_node.get('id'))
                if rel.get('type') == 'ast_prop_ddg':
                    paths.append(temp)
                    temp = []
            # Append the last node to last path and the path to all paths
            temp.append(rel.start_node.get('id'))
            paths.append(temp)
        return paths

    def getMultipleDDGPaths(self, sinkid, sourceid):
        result = self.run_cypher_query(get_ddg_paths, sinkid, sourceid)
        pair_paths = []
        path_stat = {}
        if result:
            # We are expecting multiple DDG paths
            # Break down the path into multiple paths with defalut = False property
            for path in result:
                paths = []
                temp = []
                for rel in path.relationships:
                    temp.append(rel.end_node.get('id'))
                    if rel.get('default') == False:
                        paths.append(temp)
                        temp = []
                        path_stat[rel.get('type')] = path_stat.get(rel.get('type'), 0) +1
                # Append the last node to last path and the path to all paths
                temp.append(rel.start_node.get('id'))
                paths.append(temp)
                pair_paths.append(paths)
        return pair_paths, path_stat

    def is_flows_to_edge(self, nodeid):
        return self.run_cypher_query(is_flows_to_edge_exists, nodeid)

    def get_flows_to_parent(self, nodeid):
        return self.run_cypher_query(get_flows_to_parent_node, nodeid)

    def backtrack_from_sink(self, nodeid):
        return self.run_cypher_query(backtrack_from_sink_node, nodeid)

    def getNodeOfId(self, nodeid):
        # query = "g.v(" + str(nodeid) + ")"
        # result, elapsed_time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_node_from_id, nodeid)
        logging.debug(result)
        return result

    def backtrack_from_sink_other_file(self, sinkid):
        return self.run_cypher_query(backtrack_from_sink_node_other_file, sinkid)

    def getFileIDs(self):
        # query = "g.V().filter{it.type == 'File'}.transform{it.id}"
        # fileids, elapsed_time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_all_fileids)
        return fileids

    ###
    #   Return the first element of the input. Used in list sort function
    ###
    def takeFirst(self, elem):
        return elem[0]

    #returns the file name where the node node_id is located
    def getFilenameOfNodeId(self, nodeid):
        # NOTE: We don't need loop or list here. Only one node with id
        # query = "g.V().filter{it.id == " + str(node_id)+"}.transform{it}"
        # result, elapsed_time = self.da.runTimedQuery(query)
        result = [self.run_cypher_query(get_node_from_id, nodeid)]
        #logging.debug(result)
        if result is not None:
            props = result[0].properties
            #logging.debug(props)
            funcid = props["funcid"]
            # query = "g.V().filter{it.id == " + str(funcid)+"}.transform{it}"
            # res, elapsed_time = self.da.runTimedQuery(query)
            res = [self.run_cypher_query(get_node_from_id, nodeid)]
            while (res is not None and res[0].properties)["type"] != "AST_TOPLEVEL":
                print(res[0].properties['type'])
                funcid = (res[0].properties)["funcid"]
                # query = "g.V().filter{it.id == " + str(funcid) + "}.transform{it}"
                # res, elapsed_time = self.da.runTimedQuery(query)
                res = [self.run_cypher_query(get_node_from_id, funcid)]
            filename = (res[0].properties)["name"]
            return filename

    ### given the name of a function returns the first and last line numbers of that function
    #   Input:
    #       functionName: the name of the function
    #   Output:
    #       startLineNo: the first line  number of the function
    #       endLineNo: the last line number of the function
    #Note:  case of multiple  functions having the  same name not handled.
    def getFunctionLineNumbers(self, fDeclId):
        # FIX: Returns weird result, is this the same query, and it is not funcname but id
        # NOTE: the argument is not function name but function id
        startLineNo= None
        endLineNo = None
        # get funcid of the file name
        # query = "g.V().filter(){it.id =='" + str(fDeclId) + "'}.transform{it}"
        # function, elapsed_time = self.da.runTimedQuery(query);
        function = self.run_cypher_query(get_node_from_id, fDeclId)
        if len(function) == 1:
            props = function[0].properties
            startLineNo = props["lineno"]
            endLineNo = props["endlineno"]
        return startLineNo, endLineNo

    ### Find the node of a method named 'method_name' that belongs to a class named 'class_name'
    #   Input:
    #         method_name: The target method name
    #         class_name: The class that the target method belongs to
    #         j: The Neo4j database connection
    #   Output:
    ###       node: The node of the target method
    def findMethod(self, method_name, class_name, j):
        # query = "g.V().has('name').has('classname').filter{it.name == \"" + method_name + "\" && it.classname == \"" + class_name + "\" && it.type == \"AST_METHOD\"}.id"
        # node, elapsed_time = self.da.runTimedQuery(query)
        node = self.run_cypher_query(get_ast_method_node_of_class, method_name, class_name)
        return node

    ### Get the actual source code of a method
    #   Input:
    #         class_name: The class name that the method belongs to
    #         node: the node of the target method
    #         j: The Neo4j database connection
    #   Output:
    ###       code: The actural source code of the target method
    def getMethodCode(self, class_name, node, j):
        # query = "g.V().filter{it.id == " + str(node) + "}.transform{[it.lineno, it.endlineno]}"
        # result, elapsed_time = self.da.runTimedQuery(query)[0]
        result = self.run_cypher_query(get_linenos_of_node, node)
        start = result[0]
        end = result[1]
        # query = "g.V().has('name').filter{it.type == 'AST_CLASS' && it.name == \"" + class_name + "\"}.in('FLOWS_TO').name"
        # filepath, elapsed_time = self.da.runTimedQuery(query)[0]
        filepath = self.run_cypher_query(get_filepath, class_name)
        f = open(filepath, 'r')
        code = f.readlines()[start - 1:end]
        f.close()
        return code

    ### Get the echo statemnt of a file
    #   Input:
    #         idrange: id range of some files
    #         j: The Neo4j database connection
    #   Output:
    ###       result: List of tuples that contains echo nodes and the file nodes they belongs to
    def getEchoStatements(self, filename):
        idrange = self.getIDRange(filename)
        startid = idrange[0]
        endid = idrange[1]
        # query = "g.V().filter{it.id >= " + str(startid) + " && it.id < " + str(
        #     endid) + " && (it.type == 'AST_ECHO' || it.type == 'AST_PRINT')}.id"
        # echos, elapsed_time = self.da.runTimedQuery(query)
        echos = self.run_cypher_query(get_ast_echo_print_id, startid, endid)
        result = []
        for echo in echos:
            result.append((echo, startid))
        return result

    def get_echo_statements(self, fileid, lineno=None):
        # filename should be in full filename 
        return self.run_cypher_query(get_ast_echo_print_id_adv, fileid, lineno)

    def get_function_calls(self, filename, func_name):
        return self.run_cypher_query(get_ast_func_call, filename, func_name)


    ### Analysis a file contains definitions and add all pre-defined strings to the dictionary call 'define'
    #   Input:
    #         filename: the name of the file that contains string definitions
    #         define: A dictionary that contains pre-defined strings
    #   Output:
    ###       define: The updated define dictionary
    # FIX: Remove this function. Duplicate
    """
    def getDefString(self, filename, define):
        idrange = self.getIDRange(filename)
        #logging.debug(idrange)
        for ids in idrange:
            startid = ids[0]
            endid = ids[1]
            query = "g.V().filter{it.id >= " + str(startid) + "&& it.id <" + str(
                endid) + " && it.type == 'AST_CALL'}.id"
            nodes, elapsed_time = self.da.runTimedQuery(query)
            codes = self.getCodeList(nodes)
            if codes:
                for code in codes:
                    if code[0][1] == 'define':
                        if len(code) == 3:
                            define.update({code[1][1]: code[2][1]})
                        elif len(code) > 3:
                            file = ''
                            for i in range(2, len(code)):
                                if code[i][1] in define:
                                    file += define[code[i][1]]
                                else:
                                    file += code[i][1]
                            define.update({code[1][1]: file})
                    else:
                        logging.debug(code)
        return define
    """

    ### Get the actual code of a node in the form of string
    #   Input:
    #         nodes: A list of nodes that need to get codes
    #         define: A dictionary that contains pre-defined strings
    #   Output:
    ###       result: A list of strings that represent code of each input node
    def getCodeString(self, nodes, define):
        codes = self.getCodeList(nodes)
        result = []
        for code in codes:
            file = ''
            if code:
                for x in code:
                    if x[1] in define:
                        file += define[x[1]]
                    else:
                        file += x[1]
                result.append(file)
        return result

    ### Get the actual code of a node in the form of list
    #   Input:
    #         nodes: A list of nodes that need to get codes
    #   Output:
    ###       code: A list of List. Each sublist represnets code of each input node
    def getCodeList(self, nodes):
        code = []
        for node in nodes:
            # query = "g.V().filter{it.id == " + str(
            #     node) + "}.as('do_loop').out('PARENT_OF').loop('do_loop'){it.object.has('code').count()==0}.transform{[it.id, it.code]}"
            # onecode, elapsed_time = self.da.runTimedQuery(query)
            onecode = self.run_cypher_query(get_node_with_code, node)
            # NOTE: We can sort in query itself
            onecode.sort(key=self.takeFirst)
            code.append(onecode)
        return code

    ### Get require statements code between certain lines of a file
    #   Input:
    #         idrange: The id range of the input file
    #         startline: The start line of the file that need to find the require statement
    #         endline: The end line of the file that need to find the require statement
    #         define: A dictionary that contains pre-defined strings
    #         j: The Neo4j database connection
    #   Output:
    ###       code: The actual code of what is required
    def getRequire(self, idrange, startline, endline, define):
        startid = idrange[0]
        endid = idrange[1]
        # query = "g.V().filter{it.id>=" + str(startid) + "&&it.id<" + str(endid) + "&&it.lineno>=" + str(
        #     startline) + "&&it.lineno<=" + str(
        #     endline) + "}.has('flags').filter{it.flags == ['EXEC_REQUIRE'] || it.flags == ['EXEC_REQUIRE_ONCE'] || it.flags == ['EXEC_INCLUDE']}.id"
        # require_num, elapsed_time = self.da.runTimedQuery(query)
        require_num = self.run_cypher_query(get_exec_flag_nodes, startline, endline, startid, endid)
        code = self.getCodeString(require_num, define)
        return code

    ###
    #   Get the nodes for all files
    ###
    # FIX: Duplicate function
    def getFileIDs(self):
        # query = "g.V().filter{it.type == 'File'}.transform{it.id}"
        # fileids, elapsed_time = self.da.runTimedQuery(query)
        fileids = self.run_cypher_query(get_all_fileids)
        return fileids

    """ 
    def getDDGPaths(self, attackType):
        result, elapsed_time = self.da.runTimedQuery(self.prepareDDGAnalysisQuery(attackType), True)
        return result, elapsed_time
    """

    #   Input:
    #         nodeid: The sink node
    #   Output:
    ###       result: The DDG paths that end in that sink node
    """
    def getDDGpath(self, nodeid, j):
        query = "g.V().filter{it.id == "+str(nodeid)+"}.sideEffect{m = getDDGpaths(it, [], 10, 'sql', true, {}, true)}.transform{m.id}"
        result, elapsed_time = self.da.runTimedQuery(query)
        logging.debug(result)
        return result
    """

    ### Return DDG paths from all echo statement of a file
    #   Input:
    #         idrange: The id range for the target file
    #   Output:
    ###       result: The DDG paths from all echo statement of the target file
    def getEchoDDGPaths(idrange, qi):
        echos = []
        result = []
        for ids in idrange:
            echos.append(qi.getEchoStatements(ids))
            logging.debug(echos[-1])
        for echo in echos:
            for e in echo:
                result.append(qi.getDDGpath(e[0], j))
        return result

    #def prepareDDGAnalysisQuery(attackType):
    #    if attackType == 'xss':
    #        query = """
    #            g.V().filter{it.type == TYPE_ECHO || it.type == TYPE_PRINT}
    #            .sideEffect{m = getDDGpaths(it, [], 0, 'xss', false, [], true)}
    #            .transform{m}
    #            """
    #            #
    #    elif attackType == 'sql':
    #        query = """
    #            def sql_funcs = ["mysql_query", "mysqli_query", "pg_query", "sqlite_query"];
    #            g.V().filter{it.code in sql_funcs  && isCallExpression(it.nameToCall().next())}.callexpressions()
    #            .sideEffect{m = getDDGpaths(it, [], 0, 'sql', false, [], true)}
    #            .transform{m}
    #            """
    #    return query

    ### get the required files in several files
    #   Input:
    #         idrange: The ids of several files that need to be analysised
    #         define: A dictionary that contains pre-defined strings
    #   Output:
    ###       result: A list of lists contains required files for each target file
    def analysisRequire(self, idrange, define):
        result = []
        for ids in idrange:
            requirenode = self.getRequire(ids, 0, 10000, define, j)
            result.append(requirenode)
        return result

    @lru_cache(maxsize=512)
    def getNode(self, nodeID):
        # query = "g.V().filter{it.id == " + str(nodeID) + "}.transform{it}"
        # node, elapsed_time = self.da.runTimedQuery(query)
        node = self.run_cypher_query(get_node_from_id, nodeID)
        return node


    def addCallLoop(self, depth, paths, CallLoop, nonCallLoop):
        if depth == 0:
            return paths, CallLoop, nonCallLoop
        for path in paths:
            add = []
            num = 0
            for i in range(len(path)):
                nodeid = path[i]
                if nodeid in CallLoop:
                    add.append((i + num, CallLoop[nodeid]))
                    num += len(add[-1][1])
                    continue
                elif nodeid in nonCallLoop:
                    continue
                else:
                    # query = "g.V().filter{ it.id == " + str(
                    #     nodeid) + " && it.out().filter{it.type == 'AST_CALL' && it.out('CALLS').count() != 0}.count() > 0}.id"
                    # result, elapsed_time = self.da.runTimedQuery(query)
                    result = self.run_cypher_query(get_ast_call_calls_id, nodeid)
                    logging.debug(result)
                    # NOTE: Any other way for query?
                    if result:
                        # print(result)
                        # query = "g.V().filter{ it.id == " + str(
                        #     nodeid) + " && it.out().filter{it.type == 'AST_CALL'}.count() > 0}.out().filter{it.type=='AST_CALL'}.out('CALLS').out('ENTRY').as('do_loop2').out('FLOWS_TO').loop('do_loop2'){it.object.out('FLOWS_TO').count()>0 && it.loops<100}.in('EXIT').path().transform{it.id}"
                        # looppath, elapsed_time = self.da.runTimedQuery(query)
                        looppath = self.run_cypher_query(get_cfg_path, nodeid)
                        # print(looppath)
                        #looppath=looppath[0]
                        if looppath != [None]:
                            #if looppath[0] == looppath[-1]:
                            #    looppath.pop(-1)
                            CallLoop.update({nodeid: looppath})
                            add.append((i + num, looppath))
                            num += len(add[-1][1])
                        else:
                            nonCallLoop.update({nodeid: 0})
                    else:
                        nonCallLoop.update({nodeid: 0})
                    logging.debug(path)
            for info in add:
                if depth > 1:
                    logging.debug([info[1]])
                    p, CallLoop, nonCallLoop = self.addCallLoop(depth - 1, [info[1][1:]], CallLoop, nonCallLoop)
                    p = p[0]
                    p.insert(0, info[1][0])
                    logging.debug(p)
                else:
                    p = info[1]
                path[info[0]:info[0]] = p
                # path.insert(info[0],p)
                # logging.debug(result)
        return paths, CallLoop, nonCallLoop

    def getSourceParam(self, node):
        # NOTE: We don't know what it returns, we couldn't find any case to verify the results
        sourceParam = []
        # query = "g.V().filter{it.id=="+str(node.properties['id'])+"}.as('loop1').out('PARENT_OF').loop('loop1'){it.object.code!='HTTP_GET_VARS' && it.object.code!='_GET' && it.object.code!='HTTP_POST_VARS' && it.object.code!='_POST'}.as('loop2').in('PARENT_OF').loop('loop2'){it.object.out('PARENT_OF').count() < 2}.as('loop3').out('PARENT_OF').loop('loop3'){it.object.type !='string'}"
        # result, elapsed_time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_all_parameters, node.properties['id'])
        #print(result)
        for node in result:
            if node.properties['code'][:4] not in ['HTTP', '_GET', '_POST']:
                sourceParam.append(node)
        return sourceParam

    def getCallNode(self, path):
        # NOTE: Going recursively, check this!!!
        funcNodes = []
        for i in range(len(path)):
            nodeid = path[i].properties['id']
            # query = "g.V().filter{it.id == "+str(nodeid)+"}.as('loop1').out('PARENT_OF').loop('loop1'){it.object.out('PARENT_OF').count() > 0}.path"
            # result, elapsed_time = self.da.runTimedQuery(query)
            result = self.run_cypher_query(get_last_parent_of_path, nodeid)
            if result:
                for path2 in result:
                    for node in path2:
                        # query = "g.V().filter{ it.id == " + str(node.properties['id']) + "}.out('CALLS')"
                        # funcNode, time = self.da.runTimedQuery(query)
                        funcNode = self.run_cypher_query(get_node_to_calls, node.properties['id'])
                        if funcNode:
                            #query = "g.V().filter{it.id=="+str(nodeid)+"}"
                            #nodeid, time = self.da.runTimedQuery(query)
                            if not (path[i],funcNode[0]) in funcNodes:
                                funcNodes.append((path[i], funcNode[0]))
        return funcNodes
#        return result
    def getFuncSource(self, funcNode, filename):
        idrange = self.getIDRange(filename)
        # query = "g.V().filter{it.id >"+str(idrange[0])+" && it.id<"+str(idrange[1])+"}.filter{it.lineno>="+str(funcNode.properties['lineno'])+" && it.lineno <= "+str(funcNode.properties['endlineno'])+" && it.type == 'AST_PARAM'}"
        # result, time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_ast_param_nodes, funcNode.properties['lineno'], funcNode.properties['endlineno'], idrange[0], idrange[1])
        # query = "g.V().filter{it.id >"+str(idrange[0])+" && it.id<"+str(idrange[1])+"}.filter{it.lineno>="+str(funcNode.properties['lineno'])+" && it.lineno <= "+str(funcNode.properties['endlineno'])+" && it.type == 'AST_RETURN'}"
        # result2, time2 = self.da.runTimedQuery(query)
        result2 = self.run_cypher_query(get_ast_return_nodes, funcNode.properties['lineno'], funcNode.properties['endlineno'], idrange[0], idrange[1])
        return result, result2

    def addCallDDG(self, depth, paths, CallLoop, nonCallLoop):
        if depth == 0:
            return paths, CallLoop, nonCallLoop
        for path in paths:
            add = []
            num = 0
            for i in range(len(path)):
                nodeid = path[i]
                if nodeid in CallLoop:
                    add.append((i + num, CallLoop[nodeid]))
                    num += len(add[-1][1])
                    continue
                elif nodeid in nonCallLoop:
                    continue
                else:
                    # query = "g.V().filter{ it.id == " + str(
                    #     nodeid) + " && it.out().filter{it.type == 'AST_CALL' && it.out('CALLS').count() != 0}.count() > 0}.id"
                    # result, elapsed_time = self.da.runTimedQuery(query)
                    result = self.run_cypher_query(get_ast_call_calls_id, nodeid)
                    logging.debug(result)
                    # NOTE: Any other way for query?
                    if result:
                        # print(result)
                        # query = "g.V().filter{ it.id == " + str(
                        #     nodeid) + " && it.out().filter{it.type == 'AST_CALL'}.count() > 0}.out().filter{it.type=='AST_CALL'}.out('CALLS').out('ENTRY').as('do_loop2').out('FLOWS_TO').loop('do_loop2'){it.object.out('FLOWS_TO').count()>0 && it.loops<100}.in('EXIT').path().transform{it.id}"
                        # looppath, elapsed_time = self.da.runTimedQuery(query)
                        looppath = self.run_cypher_query(get_cfg_path, nodeid)
                        # print(looppath)
                        #looppath=looppath[0]
                        if looppath != [None]:
                            #if looppath[0] == looppath[-1]:
                            #    looppath.pop(-1)
                            CallLoop.update({nodeid: looppath})
                            add.append((i + num, looppath))
                            num += len(add[-1][1])
                        else:
                            nonCallLoop.update({nodeid: 0})
                    else:
                        nonCallLoop.update({nodeid: 0})
                    logging.debug(path)
            for info in add:
                if depth > 1:
                    logging.debug([info[1]])
                    p, CallLoop, nonCallLoop = self.addCallLoop(depth - 1, [info[1][1:]], CallLoop, nonCallLoop)
                    p = p[0]
                    p.insert(0, info[1][0])
                    logging.debug(p)
                else:
                    p = info[1]
                path[info[0]:info[0]] = p
                # path.insert(info[0],p)
                # logging.debug(result)
        return paths, CallLoop, nonCallLoop

    def getSourceParam(self, node):
        # NOTE: We don't know what it returns, we couldn't find any case to verify the results
        sourceParam = []
        # query = "g.V().filter{it.id=="+str(node.properties['id'])+"}.as('loop1').out('PARENT_OF').loop('loop1'){it.object.code!='HTTP_GET_VARS' && it.object.code!='_GET' && it.object.code!='HTTP_POST_VARS' && it.object.code!='_POST'}.as('loop2').in('PARENT_OF').loop('loop2'){it.object.out('PARENT_OF').count() < 2}.as('loop3').out('PARENT_OF').loop('loop3'){it.object.type !='string'}"
        # result, elapsed_time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_all_parameters, node.properties['id'])
        #print(result)
        for node in result:
            if node.properties['code'][:4] not in ['HTTP', '_GET', '_POS']:
                sourceParam.append(node)
        return sourceParam

    def getCallNode(self, path):
        # NOTE: Going recursively, check this!!!
        funcNodes = []
        for i in range(len(path)):
            nodeid = path[i].properties['id']
            # query = "g.V().filter{it.id == "+str(nodeid)+"}.as('loop1').out('PARENT_OF').loop('loop1'){it.object.out('PARENT_OF').count() > 0}.path"
            # result, elapsed_time = self.da.runTimedQuery(query)
            result = self.run_cypher_query(get_last_parent_of_path, nodeid)
            if result:
                for path2 in result:
                    for node in path2:
                        # query = "g.V().filter{ it.id == " + str(node.properties['id']) + "}.out('CALLS')"
                        # funcNode, time = self.da.runTimedQuery(query)
                        funcNode = self.run_cypher_query(get_node_to_calls, node.properties['id'])
                        if funcNode:
                            #query = "g.V().filter{it.id=="+str(nodeid)+"}"
                            #nodeid, time = self.da.runTimedQuery(query)
                            if not (path[i],funcNode[0]) in funcNodes:
                                funcNodes.append((path[i], funcNode[0]))
        return funcNodes
#        return result
    def getFuncSource(self, funcNode, filename):
        idrange = self.getIDRange(filename)
        # query = "g.V().filter{it.id >"+str(idrange[0])+" && it.id<"+str(idrange[1])+"}.filter{it.lineno>="+str(funcNode.properties['lineno'])+" && it.lineno <= "+str(funcNode.properties['endlineno'])+" && it.type == 'AST_PARAM'}"
        # result, time = self.da.runTimedQuery(query)
        result = self.run_cypher_query(get_ast_param_nodes, funcNode.properties['lineno'], funcNode.properties['endlineno'], idrange[0], idrange[1])
        # query = "g.V().filter{it.id >"+str(idrange[0])+" && it.id<"+str(idrange[1])+"}.filter{it.lineno>="+str(funcNode.properties['lineno'])+" && it.lineno <= "+str(funcNode.properties['endlineno'])+" && it.type == 'AST_RETURN'}"
        # result2, time2 = self.da.runTimedQuery(query)
        result2 = self.run_cypher_query(get_ast_return_nodes, funcNode.properties['lineno'], funcNode.properties['endlineno'], idrange[0], idrange[1])
        return result, result2

    def addCallDDG(self, depth, paths, CallLoop, nonCallLoop):
        if depth == 0:
            return paths, CallLoop, nonCallLoop
        for path in paths:
            add = []
            num = 0
            for i in range(len(path)):
                nodeid = path[i]
                if nodeid in CallLoop:
                    add.append((i + num, CallLoop[nodeid]))
                    num += len(add[-1][1])
                    continue
                elif nodeid in nonCallLoop:
                    continue
                else:
                    query = "g.V().filter{ it.id == " + str(
                        nodeid) + " && it.out().filter{it.type == 'AST_CALL' && it.out('CALLS').count() != 0}.count() > 0}.id"
                    result, elapsed_time = self.da.runTimedQuery(query)
                    logging.debug(result)
                    if result:
                        print(result)
                        query = "g.V().filter{ it.id == " + str(
                            nodeid) + " && it.out().filter{it.type == 'AST_CALL'}.count() > 0}.out().filter{it.type=='AST_CALL'}.out('CALLS').out('ENTRY').as('do_loop2').out('REACHES').loop('do_loop2'){it.object.out('REACHES').count()>0 && it.loops<100}.in('EXIT').path().transform{it.id}"
                        looppath, elapsed_time = self.da.runTimedQuery(query)
                        print(looppath)
                        #looppath=looppath[0]
                        if looppath != [None]:
                            #if looppath[0] == looppath[-1]:
                            #    looppath.pop(-1)
                            CallLoop.update({nodeid: looppath})
                            add.append((i + num, looppath))
                            num += len(add[-1][1])
                        else:
                            nonCallLoop.update({nodeid: 0})
                    else:
                        nonCallLoop.update({nodeid: 0})
                    #logging.debug(path)
            for info in add:
                if depth > 1:
                    #logging.debug([info[1]])
                    p, CallLoop, nonCallLoop = self.addCallLoop(depth - 1, [info[1][1:]], CallLoop, nonCallLoop)
                    p = p[0]
                    p.insert(0, info[1][0])
                    #logging.debug(p)
                else:
                    p = info[1]
                path[info[0]:info[0]] = p
                # path.insert(info[0],p)
                # logging.debug(result)
        return paths, CallLoop, nonCallLoop

    def containsSource(self, path, source):
        if not path:
            return False
        if isinstance(path[0],int):
            for node in path:
                if node in source:
                    return True
        else:
            for node in path:
                if node.properties['id'] in source:
                    return True
        return False

    def printLineNumbers(self, path):
        for nodeid in path:
            node = self.getNode(nodeid)
            props = node[0].properties
            lineno = props["lineno"]
            if lineno is not None:
                logging.debug(str(nodeid) + " : " + str(lineno))

    ### Counts loops, branching statements, number of calls with no code (library calls), php-inclusions between two lines of code in a file
    # input:
    #      startline: the starting line of code
    #      endline: the ending line of code
    #      filename: the name of the file
    # output:
    #       a tuple with the number of loops, branching statements, function calls, and php inclusions
    # Used in: 1) ranking files by cyclomatic complexity between two lines of code (typically a source and an sink)
    def count_complex_constructs(self, startline, endline, filename):
        num_loops = 0
        num_ifs = 0
        num_calls = 0
        num_includes = 0
        startid, endid = self.getIDRange(filename)
        # query to find loops
        query = "g.V().filter{ it.id>=" + str(startid) + "&&it.id<" + str(endid) + "&&it.lineno >=" + str(
            startline) + " && it.out('FLOWS_TO').count()>0}"
        query += ".sideEffect{m = getLoops(it, " + str(endline) + ", 'sql')}.transform{m.id}"
        # query = "g.V().filter{it.lineno == 4}"
        # find number of loops
        #res_j = j.runGremlinQuery(query)[0]

        #res, elapsed_time = self.da.runTimedQuery(query)

        res, elapsed_time = self.da.runTimedQuery(query, True)


        if res is not None and res[0] is not None:
            num_loops = len(res[0])
        # query to find num of if statements
        query = "g.sideEffect{m = getIfStatement(it," + str(startid) + "," + str(endid) + "," + str(
            startline) + "," + str(endline) + ")}.transform{m.id}"
        #if_num_j = j.runGremlinQuery(query)[0]
        res, elapsed_time = self.da.runTimedQuery(query,True)
        if res is not None and res[0] is not None:
            num_ifs = len(res[0])
        # query to find num of calls with no code
        query = "g.sideEffect{m = getCallWithoutCode(it," + str(startid) + "," + str(endid) + "," + str(
            startline) + "," + str(endline) + ")}.transform{m.id}"
        #call_num_j = j.runGremlinQuery(query)[0]
        res, elapsed_time = self.da.runTimedQuery(query,True)
        if res is not None and res[0] is not None:
            num_calls = len(res[0])
        """for call_id in call_num:
            node = getNode(call_id, j)
            print(node)"""
        # query to find require num
        query = "g.sideEffect{m = getRequireNode(it," + str(startid) + "," + str(endid) + "," + str(
            startline) + "," + str(endline) + ")}.transform{m.id}"
        #require_num_j = j.runGremlinQuery(query)[0]
        res, elapsed_time = self.da.runTimedQuery(query,True)
        if res is not None and res[0] is not None:
            num_includes = len(res[0])
        """result = []
        for j in range(len(res)):
            r = res[j]
            logging.debug("loop ids:" + str(r))
            if r != []:
                if result == []:
                    result.append(r[0])
                for k in range(len(r)):
                    if_insert = True
                    for i in range(len(result)):
                        if set(r[k]) < set(result[i]):
                            if not str(r[k])[1:-1] in str(result[i]):
                                if_insert = False
                                break
                        elif set(r[k]) == set(result[i]):
                            if_insert = False
                            break
                        elif set(result[i]) < set(r[k]):
                            result[i] = []
                    if if_insert:
                        result.append(r[k])
        result = [value for value in result if value != []]
        return result, if_num, call_num, require_num
        """
        return num_loops, num_ifs, num_calls, num_includes


    def get_source_sink_paths(self, CFGpaths, sourceNodes):
        # We expect CFGpaths and sourceNodes both in IDs/integers
        sourceSinkPaths = []
        for path in CFGpaths:
            sink = path[-1]
            avaliable_sources = list(set(path) & set(sourceNodes))
            for source in avaliable_sources:
                source_sink_path = path[path.index(source):]
                # TODO: Check for DDG
                if self.run_cypher_query(is_ddg_dependent, sink, source):
                    sourceSinkPaths.append(source_sink_path)

        return sourceSinkPaths


    def getSourceSinkPaths(self, CFGpaths, sourceNodes):
        sourceSinkPaths = []
        for CFGpath in CFGpaths:
            path = []
            index = 0
            path_idx = 0
            flag = 0
            #self.printLineNumbers(CFGpath)
            if CFGpath:
                if not isinstance(CFGpath[0], int):
                    flag = 1
            while self.containsSource(CFGpath, sourceNodes):
                # print("Got a path")
                rang = range(len(CFGpath))
                i = 0
                if flag == 0:
                    for i in rang:
                        node = CFGpath[i]
                        if node in sourceNodes:
                            break
                if flag == 1:
                    for i in rang:
                        node = CFGpath[i]
                        if node.properties['id'] in sourceNodes:
                            break
                CFGpath = CFGpath[i:]
                #print("i="+str(i))
                logging.debug(CFGpath)
                if index == 0:
                    if flag ==0:
                        for x in CFGpath:
                            #query = "g.V().filter{it.id == " + str(x) + "}"
                            #node = self.da.runTimedQuery(query)[0]
                            node = self.getNode(x)
                            # logging.debug(node)
                            path.append(node)
                        #print(path)
                        #print(path_idx)
                        sourceSinkPaths.append(path)
                    else:
                        for x in CFGpath:
                            path.append(x)
                        sourceSinkPaths.append(path)
                else:
                    path_idx += i
                    #print(path[path_idx:])
                    #print(path_idx)
                    #if not path[path_idx:]:
                    #    exit()
                    if not path[path_idx:] in sourceSinkPaths:
                        sourceSinkPaths.append(path[path_idx:])
                if len(CFGpath) <= 1:
                    break
                CFGpath = CFGpath[1:]
                path_idx += 1
                index += 1
        return sourceSinkPaths

    def getCFGpathsBetweenLines(self, filename, startline, endline):
        IDRange = self.getIDRange(filename)

        endid = self.run_cypher_query(get_node_from_line, endline, IDRange)
        startid = self.run_cypher_query(get_node_from_line, startline, IDRange)
        #query = "g.V().filter{it.lineno =="+str(endline)+" && it.id<"+str(IDRange[1])+" && it.id>"+str(IDRange[0])+"}"
        #endids, time1 = self.da.runTimedQuery(query)
        #print(endids)
        #print(time1)
        result = []

        result = self.run_cypher_query(get_flows_to_path_adv, endid['id'], startid['id'])

        # for path in CFGpaths:
        #     path.reverse()
        #     result.append(path)
        return result

    def getReverseCFGpaths(self, nodeid, flag):
        elapsed_time = None
        if flag == 0:
            # query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').in('FLOWS_TO').simplePath().loop('do_loop'){ it.object.in('FLOWS_TO').count()>0 && it.loops < 30}.simplePath().path()"
            CFGpaths = self.run_cypher_query(get_flows_to_path, nodeid, flag)
        else:
            CFGpaths = self.run_cypher_query(get_flows_to_path, nodeid, flag)
            # query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').in('FLOWS_TO').simplePath().loop('do_loop'){ it.object.in('FLOWS_TO').count()>0 && it.loops < 30}.simplePath().path().transform{it.id}"
        # CFGpaths, elapsed_time = self.da.runTimedQuery(query)
        return CFGpaths, elapsed_time

    def getInterproceduralCFGPaths(self, depth, flag,  nodeid, CallLoop, nonCallLoop):
        paths = []
        #query = "g.V().filter{it.id == " + str(nodeid) + "}.sideEffect{m = getReviseCFGpaths(it)}.transform{m}"
        #CFGpaths, elapsed_time = self.da.runTimedQuery(query)  # dedupPath(j.runGremlinQuery(query))
        CFGpaths, elapsed_time = self.getReverseCFGpaths(nodeid, flag)
        logging.debug(CFGpaths)
        if CFGpaths:
            for path in CFGpaths:
                #for path in path_s:
                path.reverse()
                paths.append(path)
        # else:
            # print(nodeid)
            #input("")
        # for i in range(depth):
        paths, CallLoop, nonCallLoop = self.addCallLoop(depth, paths, CallLoop, nonCallLoop)
        logging.debug(CallLoop)
        return paths, CallLoop, nonCallLoop

    def getReverseDDGpaths(self, nodeid, flag):
        elapsed_time = None
        if flag == 0:
            # query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').in('REACHES').simplePath().loop('do_loop'){ it.object.in('REACHES').count()>0 && it.loops < 30}.simplePath().path()"
            DDGpaths = self.run_cypher_query(get_reaches_to_path, nodeid, flag)
        else:
            DDGpaths = self.run_cypher_query(get_reaches_to_path, nodeid, flag)
            # query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').in('REACHES').simplePath().loop('do_loop'){ it.object.in('REACHES').count()>0 && it.loops < 30}.simplePath().path().transform{it.id}"
        # DDGpaths, elapsed_time = self.da.runTimedQuery(query)
        return DDGpaths, elapsed_time

    def getInterproceduralDDGPaths(self, depth, flag, ifdebug,  nodeid, CallLoop, nonCallLoop):
        paths = []
        #query = "g.V().filter{it.id == " + str(nodeid) + "}.sideEffect{m = getReviseCFGpaths(it)}.transform{m}"
        #CFGpaths, elapsed_time = self.da.runTimedQuery(query)  # dedupPath(j.runGremlinQuery(query))
        DDGpaths, elapsed_time = self.getReverseDDGpaths(nodeid, flag)
        if ifdebug!=0:
            logging.debug(DDGpaths)
        if DDGpaths:
            for path in DDGpaths:
                #for path in path_s:
                path.reverse()
                paths.append(path)
        else:
            print(str(nodeid)+" do not have DDG path")
            #input("")
        # for i in range(depth):
        paths, CallLoop, nonCallLoop = self.addCallLoop(depth, paths, CallLoop, nonCallLoop)
        if ifdebug!=0:
            logging.debug(CallLoop)
        return paths, CallLoop, nonCallLoop

    def getUnreversedReverseDDGpaths(self, nodeid, flag):
        if flag == 0:
            query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').out('REACHES').simplePath().loop('do_loop'){ it.object.out('REACHES').count()>0 && it.loops < 30}.simplePath().path()"
        else:
            query = "g.V().filter{it.id == " + str(nodeid) + "}.as('do_loop').out('REACHES').simplePath().loop('do_loop'){ it.object.out('REACHES').count()>0 && it.loops < 30}.simplePath().path().transform{it.id}"
        DDGpaths, elapsed_time = self.da.runTimedQuery(query)
        return DDGpaths, elapsed_time

    def getUnreversedInterproceduralDDGPaths(self, depth, flag, ifdebug,  nodeid, CallLoop, nonCallLoop):
        paths = []
        #query = "g.V().filter{it.id == " + str(nodeid) + "}.sideEffect{m = getReviseCFGpaths(it)}.transform{m}"
        #CFGpaths, elapsed_time = self.da.runTimedQuery(query)  # dedupPath(j.runGremlinQuery(query))
        DDGpaths, elapsed_time = self.getUnreversedReverseDDGpaths(nodeid, flag)
        if ifdebug!=0:
            logging.debug(DDGpaths)
        if DDGpaths:
            for path in DDGpaths:
                #for path in path_s:
                #path.reverse()
                paths.append(path)
        #else:
        #    print(str(nodeid)+" do not have DDG path")
            #input("")
        # for i in range(depth):
        paths, CallLoop, nonCallLoop = self.addCallLoop(depth, paths, CallLoop, nonCallLoop)
        if ifdebug!=0:
            logging.debug(CallLoop)
        return paths, CallLoop, nonCallLoop

    # Finds the range of node ids in the CPG that belong to the file 'filename'
    #   Input:
    #          filename: Full path of the target file
    #   Output:
    ###        endid: The range of nodes that are belongs to the target file in form of tuple
    def getIDRange(self, filename):
        # NOTE: Is there any other way on how to find endid
        # query to find id range of the input file
        # query = "g.V().filter{it.name =='" + filename + "'}.transform{it.id}"
        # startid, elapsed_time = self.da.runTimedQuery(query)
        startid = self.run_cypher_query(get_filenode_from_name, filename)
        # print("startid, ", startid)
        if not startid:
            return -1, -1
        startid = startid[0]
        # query = "g.V().filter{it.type == 'File'}.transform{it.id}"
        # fileids, elapsed_time = self.da.runTimedQuery(query)
        fileids = self.run_cypher_query(get_all_fileids)
        endid = startid
        for x in fileids:
            if x > startid:
                endid = x
                break
        if startid == endid:
            endid += 100000
        return startid, endid

    # Finds the node ids of the source statements _GET, _POST.
    #   Input:
    #          idrange: the range of node id-s in the CPG that belong to that file (see getIDRange)
    #   Output:
    ###        sourceNodes: the list of nodes that represent an assignment from a _GET/ _POST superglobal
    def getSourceNodes(self, filename):
        #idrange = self.getIDRange(filename)
        # print(idrange)
        # print(idrange)
        fileid = self.run_cypher_query(get_php_file_node_query, filename)
        #startid = idrange[0]
        #endid = idrange[1]
        # query = "g.V().has('code').filter{it.id >= " + str(startid) + " && it.id < " + str(
        #     endid) + " && (it.code == '_POST' || it.code == '_GET' || it.code == 'HTTP_POST_VARS' || it.code == 'HTTP_GET_VARS')}.as('do_loop').in('PARENT_OF').loop('do_loop'){it.object.both('FLOWS_TO').count()==0}.id"
        # sourceNodes = self.da.runTimedQuery(query)[0]
        # print(startid, endid)
        sourceNodes = self.run_cypher_query(get_nodes_by_code, fileid)
        # result = []
        # for sourceNode in sourceNodes:
        #    result.append((sourceNode,startid))
        return sourceNodes

    def get_source_nodes(self, fileid):
        # Full filename with full path
        return self.run_cypher_query(get_nodes_by_code_adv, fileid)

    def get_ddg_dependencies(self, nodeid):
        return self.run_cypher_query(backtrack_from_sink_node, nodeid)

    ################################

    def get_conditional_stmt_if(self, nodeid):
        return self.run_cypher_query(get_conditional_parent_if, nodeid)

    def get_conditional_stmt_while(self, nodeid):
        return self.run_cypher_query(get_conditional_parent_while, nodeid)

    def get_conditional_stmt_switch(self, nodeid):
        return self.run_cypher_query(get_conditional_parent_switch, nodeid)

    def get_conditional_stmt_foreach(self, nodeid):
        return self.run_cypher_query(get_conditional_parent_foreach, nodeid)

    def get_reaches_edges(self, nodeid):
        return self.run_cypher_query(get_reaches_edges_query, nodeid)

    def get_all_paths_of_function(func_definition_node):
        return 1
    ################################

    def getSQLSinks(self, filename):
        return []

    def get_function_decl(self, node_id):
        query = "g.V().filter{it.id==" + str(node_id) + "}.out('CALLS')"
        result, elapsed_time = self.da.runTimedQuery(query)
        if len(result) > 0:
            return result[0]
        else:
            return None

    """
    def getCFGPaths(self, startline, endline, filename, CallLoop, nonCallLoop):
        startid, endid = self.getIDRange(filename)
        logging.debug(startid, endid)
        exist_node = {}
        paths = []
        query = "g.V().filter{it.id>=" + str(startid) + "&&it.id<" + str(endid) + "&&it.lineno >=" + str(
            startline) + " && it.lineno <" + str(endline) + " && it.out('FLOWS_TO').count()==0}.id"
        ids, elapsed_time = self.da.runTimedQuery(query)
        for id in ids:
            exist_node.update({id: 1})
        for id in range(startid, endid):
            if id not in exist_node:
                query = "g.V().filter{it.id==" + str(id) + "&&it.lineno >=" + str(startline) + " && it.lineno <" + str(
                    endline) + " && it.out('FLOWS_TO').count()>0}.sideEffect{m = getCFGpaths(it, " + str(
                    endline) + ", 'sql')}.transform{m.id}"
                #    query = "g.V().filter{it.id>="+str(startid)+"&&it.id<"+str(endid)+"&&it.lineno >="+str(startline)+" && it.out('FLOWS_TO').count()>0}.sideEffect{m = getCFGpaths(it, "+str(endline)+", 'sql')}.transform{m.id}"
                # query = "g.V().filter{it.lineno == 4}"
                CFGpaths, elapsed_time = self.da.runTimedQuery(query)  # dedupPath(j.runGremlinQuery(query))
                # logging.debug(CFGpaths)
                for path_s in CFGpaths:
                    for path in path_s:
                        paths.append(path)
                        # logging.debug(path)
                        for node in path:
                            if node in exist_node:
                                exist_node.update({node: exist_node[node] + 1})
                            else:
                                exist_node.update({node: 1})
        # paths,CallLoop,nonCallLoop = addCallLoop(paths,CallLoop,nonCallLoop,j)
        # logging.debug(CallLoop)
        return paths, CallLoop, nonCallLoop
    """

    #checked
    #returns a map of {function definition id: list of sensitivities}
    def get_all_functions_sensitivity_levels(self, sensitive_instructions_list):
        # get all method and function definitions
        # for each function definition count all CONTROL_FLOWS_TO (cfg) paths (let total count be A)
        # find the instructions in the function that are in the sensitive_functions_list (e.g., echo, _GET, etc)
        # for each of these instructions count how many FLOWS_TO (cfg) paths it is in (let count be N_i).
        # Return fraction Sum(N_i)/A. Challenge: if there are more than 1 sensitive instructions the sets of sensitive paths may overlap

        # It can be made recursive but will only do the first level.
        tracker_counter = 0
        function_sensitivity_levels = {}
        # get all method and function definitions
        func_and_method_definitions = self.run_cypher_query(get_function_and_method_defs)

        count = 0
        for method_node in func_and_method_definitions:
            tracker_counter += 1
            count += 1
            # find the instructions in the function that are in the sensitive_functions_list (e.g., echo, _GET, etc)
            sensitive_instructions_in_method = self.get_sensitive_instructions(method_node, sensitive_instructions_list)

            if len(sensitive_instructions_in_method) == 0: #no sensitive instructions in this function
                function_sensitivity_levels[method_node] = 0 #sensitive level is set to 0
                continue

            #count total number of paths A inside the method
            print("Counting all paths inside a method...")
            total_no_paths, the_paths = self.count_cfg_paths_in_function(method_node)

            # the_paths = self.run_cypher_query(get_actual_paths, method_node)
            print("Done counting paths inside a method...they are: ", total_no_paths, len(the_paths))
            # if total_no_paths == 211 or total_no_paths == 212:
            #     the_paths = []
            #     total_no_paths = 0

            if total_no_paths == 0:
                print("Function with 0 paths, node id: " + str(method_node.properties["id"]))
                continue
            # print("the paths arte:", the_paths)
            no_paths_with_sensitive_instructions = 0
            if the_paths is not None:
                for instr in sensitive_instructions_in_method:
                    instr_id = instr.properties["id"]
                    for path in the_paths:
                        for x in range(0, len(path.nodes)):
                            node_id = path.nodes[x]['id']
                        # node_id = path.nodes[0]['id']
                            if node_id == instr_id:
                                no_paths_with_sensitive_instructions += 1
                                break

            # no_paths_with_sensitive_instructions = self.count_cfg_paths_instruction_in(sensitive_instructions_in_method, method_node)
            if no_paths_with_sensitive_instructions is not None:
                print("The number of paths found are: ", no_paths_with_sensitive_instructions)
                sensitivity_level = no_paths_with_sensitive_instructions/total_no_paths #should be the execution likelihood
            else:
                sensitivity_level = 0
            #debug
            print("Done with query and we are here...")
            if sensitivity_level > 1 or sensitivity_level <= 1:
                filename = self.run_cypher_query(get_filename_of_node, method_node.properties['id'])[0]
                method_name = method_node.properties["name"]
                print(str(count) + " out of " + str(no_methods))
                if sensitivity_level > 1:
                    print("ALERT: Sensitivity level > 1: " + filename + ":" + method_name + ": " + str(sensitivity_level))
                else:
                    print("Sensitivity level: " + filename + ":" + method_name + ": " + str(sensitivity_level))
            #end debug
            print("Testing this....")
            function_sensitivity_levels[method_node.properties["id"]] = sensitivity_level
            print("Beyond testing...")
        return function_sensitivity_levels

    def count_cfg_paths_instruction_in(self, sensitive_instruction, method_node):
        entry_and_exit_nodes = self.run_cypher_query(get_entry_and_exit_nodes, method_node)
        print("Going into the query now...")
        no_paths = self.run_cypher_query(count_cfg_paths_instruction_is_in, sensitive_instruction, entry_and_exit_nodes, method_node)
        return no_paths

    #checked
    def get_sensitive_instructions(self, method_node, sensitive_instructions_list):
        #given a method instruction, we only want to check those nodes in the graph that have code words
        code_nodes = self.run_cypher_query(get_nodes_with_code, method_node, sensitive_instructions_list)
        if len(code_nodes) == 0:
            return []
        sensitive_instructions = []
        for code_node in code_nodes:
            instruction = self.run_cypher_query(get_parent_instruction, code_node)
            if isinstance(instruction, list) and len(instruction) == 0:
                continue
            if instruction.properties["type"] == "AST_ARG_LIST": #the sensitive word appears as an argument
                continue
            sensitive_instructions.append(instruction)
        return sensitive_instructions

    #checked
    #Use leaf multiplicities to count the number of paths
    def count_cfg_paths_in_function(self, node):
        entry_and_exit_nodes = self.run_cypher_query(get_entry_and_exit_nodes, node)

        print("Done obtaining the entry exit nodes...")
        total_no_paths = []
        the_paths = []
        all_paths = 0
        no_paths = self.run_cypher_query(count_cfg_paths_between_nodes, entry_and_exit_nodes)
        print("no paths is: ", no_paths)
        if no_paths is None: #couldn't finish on time...
            i_tracker = False
            y_tracker = False
            print("Running sub query now...")
            for i in range(1, 1000):
                no_paths_temp = self.run_cypher_query(count_cfg_paths_between_nodes_take_two, entry_and_exit_nodes, i)
                print("the paths are: ", no_paths_temp, i)
                if no_paths_temp is None: #can't find paths from 0 itself, just terminate
                    break
                if no_paths_temp is not None and type(no_paths_temp) == int and no_paths_temp > 0:
                    print("Obtained count, now returning them...")
                    all_paths += no_paths_temp
                    the_paths_temp = self.run_cypher_query(get_actual_paths_take_two, entry_and_exit_nodes, i)
                    # for path in the_paths_temp:
                    #     for x in path.nodes:
                    #     print(path.nodes, len(path.nodes))
                    #     print(path.nodes[0]['id'])
                    if the_paths_temp is not None:
                        the_paths += the_paths_temp
                    else:
                        break
                if type(no_paths_temp) == int and no_paths_temp > 0:
                    i_tracker = True
                if type(no_paths_temp) == int and no_paths_temp == 0:
                    y_tracker = True
                if (i_tracker == True and ((type(no_paths_temp) == int and no_paths_temp == 0) or no_paths_temp is None) ) or \
                        (y_tracker == True and no_paths_temp is None):
                    break




        else:

            print("Done obtaining total number of paths...")
            the_paths_temp = self.run_cypher_query(get_actual_paths, entry_and_exit_nodes)
            if the_paths_temp is None:
                i_tracker = False
                y_tracker = False
                for i in range(1, 1000):
                    the_paths_temp = self.run_cypher_query(get_actual_paths_take_two, entry_and_exit_nodes, i)
                    if the_paths_temp is None:  # can't find paths from 0 itself, just terminate
                        break
                    if the_paths_temp is not None and len(the_paths_temp) > 0:
                        print("Obtained count, now returning them...")
                        all_paths += len(the_paths_temp)
                        the_paths += the_paths_temp
                    if len(the_paths_temp) > 0:
                        i_tracker = True
                    if len(the_paths_temp) == 0:
                        y_tracker = True
                    if (i_tracker == True and (len(the_paths_temp) == 0) or the_paths_temp is None) or \
                            (y_tracker == True and the_paths_temp is None):
                        break
                print("Length of the_paths from sub query is: ", len(the_paths))
            else:
                the_paths += the_paths_temp
                all_paths += no_paths

        return all_paths, the_paths


    def get_all_identifier_occurrences(self):
        #collect all the identifiers that are present as a part of function calls, methods and variables
        calls_identifiers = self.run_cypher_query(get_all_calls_identifiers) #all function calls (AST_CALL)
        methods_identifiers = self.run_cypher_query(get_all_methods_identifiers) #all method calls as [object, method] (AST_METHOD_CALL)
        variable_identifiers = self.run_cypher_query(get_all_variable_identifiers) #all variables (AST_VAR)

        #count each of the occurrences
        calls_occurrences = {}
        for call in calls_identifiers:
            if call not in calls_occurrences:
                calls_occurrences[call] = 1
            else:
                calls_occurrences[call] += 1
        methods_occurrences = {}
        for method in methods_identifiers[0]:
            if method[0] is not None and method[1] is not None:
                name = method[0] + "->" + method[1]
                if name not in methods_occurrences:
                    methods_occurrences[name] = 1
                else:
                    methods_occurrences[name] += 1
        #we split the variables into those that are superglobals and those that are not
        variable_occurrences = {}
        superglobal_occurrences = {}
        for variable in variable_identifiers[0]:
            if variable != 'this':
                if variable not in ["_GET", "GET", "_POST", "POST", "_SERVER", "SERVER", "_REQUEST", "REQUEST", "_FILES", "FILES",
                "_SESSION", "SESSION", "_COOKIE", "COOKIE"]:
                    if variable not in variable_occurrences:
                        variable_occurrences[variable] = 1
                    else:
                        variable_occurrences[variable] += 1
                else:
                    if variable not in superglobal_occurrences:
                        superglobal_occurrences[variable] = 1
                    else:
                        superglobal_occurrences[variable] += 1
        return {"calls_occurrences": calls_occurrences, "methods_occurrences": methods_occurrences, "variable_occurrences": variable_occurrences, "superglobal_occurrences": superglobal_occurrences}


    def dedupPath(self, CFGPaths):
        final_path = []
        for paths in CFGPaths:
            for path in paths:
                if_insert = True
                for exist_path in final_path:
                    if str(path)[1:-1] in str(exist_path):
                         if_insert = False
                         break
                if if_insert:
                    final_path.append(path)
        return final_path




    ### Analyse a file containing definitions and add all pre-defined strings to the dictionary call 'define'
    #   This is useful for those applications that define a bunch of constants in the same file. E.g., configure.php:   define('DB_SERVER', 'localhost');
    #   This is needed to be able to resolve the php include files statically (e.g.,   require(DIR_WS_INCLUDES . 'template_top.php');)
    #   Input:
    #         filename: the name of the file that contains string definitions
    #         define: A dictionary that contains pre-defined strings
    #   Output:
    ###       define: The updated define dictionary
    """
    def getDefString(self, filename, define):
        # FIX: How is this supposed to return list of ids??
        # Everyother place this function only returns one list of startid and endid
        idrange = self.getIDRange(filename)
        logging.debug(idrange)
        for ids in idrange:
            startid = ids[0]
            endid = ids[1]
            query = "g.V().filter{it.id >= "+str(startid)+"&& it.id <"+str(endid)+" && it.type == 'AST_CALL'}.id"
            nodes, elapsed_time = self.da.runTimedQuery(query)
            nodes = self.run_cypher_query(get_ast_class_id, startid, endid)
            codes = self.getCodeList(nodes)
            if codes:
                for code in codes:
                    if code[0][1] == 'define':
                        if len(code) == 3:
                            define.update({code[1][1]:code[2][1]})
                        elif len(code) >3:
                            file = ''
                            for i in range(2,len(code)):
                                if code[i][1] in define:
                                    file+=define[code[i][1]]
                                else:
                                    file+=code[i][1]
                            define.update({code[1][1]:file})
                    else:
                        logging.debug(code)
        return define
    """

# qi = CPGQueryInterface()
# print(qi.getNodeOfId(50))
# print(len(qi.getFileIDs()))
# print(qi.total_time)
# print(qi.getFilenameOfNodeId(320))
# print(qi.getFilenameOfNodeId(50))
# print(qi.findMethod('get_registry', 'SimplePie', None))
# print(qi.getMethodCode('PasswordHash', 1352, None))
# print(qi.getIDRange('class-simplepie.php'))
# print(qi.getEchoStatements('class-simplepie.php'))
# print(qi.getCodeList([26, 49]))
# print(qi.getRequire([586, 2098], 0, 500, {}))
# print(qi.getSourceNodes('/var/www/html/schoolmate_small/ManageTeachers.php'))
# print(qi.getReverseCFGpaths(26, 0))
# path, _ = qi.getReverseCFGpaths(26, 0)
# print(qi.getCallNode(path[0]))

###### TEST ######
# print(qi.addCallLoop())

###### FIX ######
# print(qi.getDefString('class-simplepie.php', {}))

# print(qi.total_time)
