import itertools
from neo4j import GraphDatabase
from datetime import datetime
import json
from migration_neo4j_4.cypher_queries import *
from satpath_evaluate import source_to_sink_data, get_file_entry_node, file_to_sink_data
from CPGQueryInterface import CPGQueryInterface
import warnings
import re
warnings.filterwarnings("ignore")
import globals
# from generate_path_adv import get_sinks

uri = 'bolt://127.0.0.1:' + str(globals.NEO4J_BOLT_PORT)
user = 'neo4j'
password = 'user'

#this file is responsible for adding new properties and edges to the CPG:
#fileid, filename, is_db property, is_source property
#edges: REACHES edges between function call arguments and function definitions parameters
#       REACHES edges between class properties for getters and setters.
#

def print_paths(paths, l1, l2, result_summary, fileid):
    """
        Print paths from one line to another line, consisting one or more nodes.
        For now, just pring ids of nodes.
    """
    # print("Possible paths between lines {l1} and {l2} in file {fileid}".format(l1=l1, l2=l2, fileid=fileid))
    for path_i in range(len(paths)):
        print("\nPath {}".format(path_i + 1))
        for node in paths[path_i]['path'].nodes:
            print("{}".format(node['lineno']), end=" <- ")
        # print("{} - {}".format(path.start_node['id'], path.end_node['id']))
    print("Total number of possible paths: {}".format(len(paths)))
    # TODO: Fix why it always returns 0?
    # TODO: What is the time parameter of this result?
    # print("Total: {} s".format(result_summary.result_available_after +result_summary.result_consumed_after/1000.0))
    print("Result avaliable after: {} ms\nConsumed after: {} ms\nTotal: {} s".format(result_summary.result_available_after,
        result_summary.result_consumed_after, (result_summary.result_available_after +result_summary.result_consumed_after)/1000.0))



def get_total_ast(tx, label):
    """
        Get total number of nodes of given type in database.
    """
    result = tx.run("MATCH (:{label}) RETURN COUNT(*) AS total".format(label=label))
    return result.single()['total']

def get_total_relationships(tx, relationship_type):
    """
        Get total number of given type of relationships in db.
    """
    result = tx.run("match (n)-[r:{relationship_type}]->() return distinct count(r) as total".format(relationship_type=relationship_type))
    return result.single()['total']

def get_total_ast_types(tx, ast_type):
    """
        Get total number of AST types nodes in db.
    """
    result = tx.run("MATCH (:AST {{type: '{ast_type}'}}) RETURN COUNT(*) AS total".format(ast_type=ast_type))
    return result.single()['total']


def find_nodes_depth(tx, ast_node_id, depth_size):
    """
        Get all nodes related to ast_node_id till depth_size. Any relationship.
    """
    result = tx.run("MATCH path=(AST:a {{id:{ast_node_id}}})-[*{depth_size}]-() RETURN path".format(depth_size=depth_size,
                                                                                                     ast_node_id=ast_node_id))
    return result

def find_path(tx, lineno1, lineno2, fileid):
    result = tx.run("MATCH path=(first:AST {{fileid: {fileid}, lineno: {lineno1}}})-[:FLOWS_TO*]->(last:AST {{fileid: {fileid}, lineno: {lineno2}}}) RETURN path".format(
    lineno1=lineno1, lineno2=lineno2, fileid=fileid))
    # result = tx.run("MATCH path=(first:AST {{fileid: {fileid}, lineno: {lineno1}}})-[:FLOWS_TO*]->(last:AST {{fileid: {fileid}, lineno: {lineno2}}}) using index seek first:AST(fileid, lineno) using index seek last:AST(fileid, lineno) RETURN path".format(
    # lineno1=lineno1, lineno2=lineno2, fileid=fileid))
    # result = tx.run("MATCH path=(first:AST {{fileid: {fileid}, lineno: {lineno1}}})-[:FLOWS_TO*]->(last:AST {{fileid: {fileid}, lineno: {lineno2}}}) using index seek first:AST(fileid) using index seek first:AST(lineno) using index seek last:AST(fileid) using index seek last:AST(lineno) RETURN path".format(
    # lineno1=lineno1, lineno2=lineno2, fileid=fileid))
    # result = tx.run("MATCH (first:AST), (last:AST) where first.fileid={fileid} and first.lineno={lineno1} and last.fileid={fileid} and last.lineno={lineno2} match path=(first)-[:FLOWS_TO*]->(last) RETURN path".format(
    #    fileid=fileid, lineno1=lineno1, lineno2=lineno2))
    return result

def find_directory(tx, file_id):
    """
        Get the directory of given file.
    """
    result = tx.run("MATCH (f:Filesystem {{id: '{file_id}'}})<-[:DIRECTORY_OF]-(d:Filesystem) RETURN d".format(file_id=file_id)).single()
    return result.data()['d'] if result != None else None

def find_node(tx, node_type, node_id):
    """
        Find node of given node_type and with node_id value in id property
    """
    result = tx.run("MATCH (a:{node_type}) where a.id = {node_id} return a".format(node_type=node_type, node_id=node_id))
    return result

def get_file_ids(tx):
    result = tx.run("MATCH (a:Filesystem {type: 'File'})-[:FILE_OF]->(f:AST) return collect(f.id) as ids").single()
    return result

def get_file_ids_names(tx):
    result = tx.run("MATCH (a:Filesystem {type: 'File'})-[:FILE_OF]->(f:AST)-[:ENTRY]->(c:Artificial) with c, f order by f.id return collect(distinct [f.id, c.name]) as result").single()
    return result

def get_filesystem_ids(tx):
    result = tx.run("MATCH (a:Filesystem) return collect(a.id) as ids")
    return result

def get_null_nodes(tx):
    result = tx.run("MATCH (a:AST {type: 'NULL'}) return collect(a.id) as ids")
    return result

def remove_all_null_nodes(tx):
    result = tx.run("match (b)-[:FLOWS_TO]->(a:AST {type: 'NULL'})-[:FLOWS_TO]->(c) merge (b)-[:FLOWS_TO]->(c) detach delete a")
    # result = tx.run("match (a:AST {t")
    return True

# def get_flows_to_if_exist(tx):
#     result = tx.run("MATCH (a")

def set_fileid(tx, start, end, fileid):
    result = tx.run("MATCH (a) where a.id >= {start} and a.id < {end} set a.fileid = {fileid}".format(
        start=start, end=end, fileid=fileid))
    return True

def set_file_id_name(tx, start, end, fileid, filename):
    result = tx.run("MATCH (a) where a.id >= {start} and a.id < {end} set a.fileid = {fileid} set a.file_name='{filename}'".format(
        start=start, end=end, fileid=fileid, filename=filename))
    return True

def set_last_fileid(tx, start, fileid):
    result = tx.run("MATCH (a) where a.id >= {start} set a.fileid = {fileid}".format(
        start=start, fileid=fileid))
    return True    

def set_last_file_id_name(tx, start, fileid, filename):
    result = tx.run("MATCH (a) where a.id >= {start} set a.fileid = {fileid} set a.file_name='{filename}'".format(
        start=start, fileid=fileid, filename=filename))
    return True

def set_filename(tx, nodeid):
    result = tx.run("MATCH (a:Filesystem)-[:FILE_OF]->(f:AST)-[:ENTRY]->(c:Artificial) WHERE a.type='File' and a.id={nodeid} SET a.full_name=c.name RETURN true".format(nodeid=nodeid))    
    # result = tx.run("MATCH (a:Filesystem)-[:FILE_OF]->(f:AST)-[:ENTRY]->(c:Artificial) WHERE a.id={nodeid} SET a.full_name=c.name RETURN true".format(nodeid=nodeid))
    # print(result, nodeid)
    return True if result.single() else False

def get_all_func_declarations(tx):
    result = tx.run("""
        match (func_decl:AST)-[:PARENT_OF]->(paraml:AST)-[:PARENT_OF]->(param:AST)-[:PARENT_OF]->(params:AST)
        where func_decl.type in ['AST_FUNC_DECL'] and paraml.type in ['AST_PARAM_LIST'] and param.type in ['AST_PARAM']
        and exists(params.code) return collect([func_decl.id, param.id]) as funcs""").single()
    return result

def get_func_calls(tx, funcid):
    result = tx.run("""
            match (func_decl)<-[:CALLS]-(func_calls:AST)-[:PARENT_OF*..3]->(ast_var:AST)
            where func_decl.id={funcid} and func_calls.type in ['AST_CALL'] and ast_var.type in ['AST_VAR']
            return count(func_calls) as call_total, count(ast_var) as var_total""".format(funcid=funcid)).single()
    return result

def get_func_calls_node(tx, lineno, fileid):
    result = tx.run("""
            match (func_calls:AST)-[:PARENT_OF]->(a)-[:PARENT_OF]->(b)
            where func_calls.lineno={lineno} and func_calls.fileid={fileid} and func_calls.type='AST_CALL' and a.type='AST_NAME'
            and b.safe=True
            return collect(distinct b.code) as result""".format(lineno=lineno, fileid=fileid)).single()
    return result

def get_func_calls_node_all(tx, lineno, fileid):
    result = tx.run("""
            match (func_calls:AST)-[:PARENT_OF]->(a)-[:PARENT_OF]->(b)
            where func_calls.lineno={lineno} and func_calls.fileid={fileid} and func_calls.type='AST_CALL' and a.type='AST_NAME'
            return collect(distinct b.code) as result""".format(lineno=lineno, fileid=fileid)).single()
    return result

def get_ast_prop_nodeids(tx, varname, classname):
    result = tx.run("""
            match (a)-[:PARENT_OF]->(b)
            where a.type in ['AST_PROP'] and b.code='{varname}' and b.classname='{classname}'
            match (a)<-[:PARENT_OF*..5]-(c)
            where a.type in ['AST_PROP'] and exists((c)-[:FLOWS_TO]->())
            return collect([a.id, c.id, c.type]) as props
        """.format(varname=varname, classname=classname)).single()
    return result

def add_ddg(tx, fromnode, tonode, rtype, tablename=None, attribute=None):
    # 242, 12421, 'sql_ddg'
    if not tablename or not attribute:
        result = tx.run("""
                match (a) match (b) where a.id={fromnode} and b.id={tonode} merge (a)-[r:REACHES]->(b) set r.default=False set r.type='{rtype}' return True""".format(
                    fromnode=fromnode, tonode=tonode, rtype=rtype)).single()
    else:
        result = tx.run("""
                match (a) match (b) where a.id={fromnode} and b.id={tonode} merge (a)-[r:REACHES]->(b) set r.default=False set r.type='{rtype}' set r.tablename='{tablename}' set r.attribute='{attribute}' return True""".format(
                    fromnode=fromnode, tonode=tonode, rtype=rtype, tablename=tablename, attribute=attribute)).single()

    return result

def remove_edges(tx, type):
    tx.run("""
        match ()-[r:REACHES]->()
        where r.default=False and r.type='{type}'
        delete r
    """.format(type=type))

def create_index(tx):
    result = tx.run("create index ifileid for (a:AST) on (a.fileid)")
    result = tx.run("create index ilineno for (a:AST) on (a.lineno)")
    result = tx.run("create index iffileid for (a:Filesystem) on (a.fileid)")
    result = tx.run("create index itype for (a:AST) on (a.type)")
    return True

def remove_self_rels(tx):
    result = tx.run("match (a)-[r]->(a) delete r")
    return True

def add_ddg_pairs(tx, ddg_node_pairs, rtype):
    # [[1,2],[3423,232]....]
    result = tx.run("""
            with {ddg_node_pairs} as pairs
            unwind pairs as pair
            match (a)
            match (b) where a.id=pair[0] and b.id=pair[1]
            merge (a)-[r:REACHES]->(b)
            set r.default=False
            set r.type='{rtype}'

            return True
        """.format(ddg_node_pairs=ddg_node_pairs, rtype=rtype))
    return result

def add_cfg_pairs(tx, cfg_node_pairs, rtype):
    # [[1,2],[3423,232]....]
    result = tx.run("""
            with {cfg_node_pairs} as pairs
            unwind pairs as pair
            match (a)
            match (b) where a.id=pair[0] and b.id=pair[1]
            merge (a)-[r:FLOWS_TO]->(b)
            set r.type='{rtype}'

            return True
        """.format(cfg_node_pairs=cfg_node_pairs, rtype=rtype))
    result = result.single()
    #result_summary = result.summary()
    return result



def get_all_func_call_defs_args(tx):
    """
        {
          "func": 31000,
          "details": [
            {
              "acall": 30186,
              "aargs": [
                30190
              ]
            }
          ],
          "params": [
            31004,
            31008
          ]
        }
    result = tx.run(
                match (func_decl:AST)
                where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((func_decl)<-[:CALLS]-())
                with collect(func_decl) as funcs

                unwind funcs as func
                match (func)-[:PARENT_OF]->(paraml:AST)-[:PARENT_OF]->(param:AST)
                where paraml.type in ['AST_PARAM_LIST'] and param.type in ['AST_PARAM']
                with func, param order by param.childnum
                with func, collect(param.id) as params
                match (b)-[:CALLS]->(func)
                with func, params, collect(b) as acalls

                unwind acalls as acall
                match (acall)-[:PARENT_OF]->(arg_list:AST)-[:PARENT_OF]->(args:AST)
                where arg_list.type in ['AST_ARG_LIST']
                with func, params, acall, args order by args.childnum   
                with func, params, {acall: acall.id, aargs: collect(args.id)} as acalldetail
                with {func: func.id, params: params, details: collect(acalldetail)} as res
                return collect(res) as result
        ).single()
    """
    result = tx.run("""
                match (func_decl:AST)
                where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((func_decl)<-[:CALLS]-())
                with collect(func_decl) as funcs

                unwind funcs as func
                match (func)-[:PARENT_OF]->(paraml:AST)-[:PARENT_OF]->(param:AST)
                where paraml.type in ['AST_PARAM_LIST'] and param.type in ['AST_PARAM']
                with func, param order by param.childnum
                with func, collect(param.id) as params
                match (b)-[:CALLS]->(func)
                with {func: func.id, params: params, acalls: collect(b.id)} as res
                return collect(res) as result
        """).single()

    return result

def create_all_func_call_defs_args(tx):
    result = tx.run("""
                match (func_decl:AST)
                where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((func_decl)<-[:CALLS]-())
                with collect(distinct func_decl) as funcs

                unwind funcs as func
                match (func)-[:PARENT_OF]->(paraml:AST)-[:PARENT_OF]->(param:AST)
                where paraml.type='AST_PARAM_LIST' and param.type='AST_PARAM'
                with func, param order by param.childnum
                with func, collect(param) as params
                match (b)-[:CALLS]->(func)
                with func, params, collect(distinct b) as acalls

                unwind acalls as acall
                match (acall)-[:PARENT_OF]->(arg_list:AST)-[:PARENT_OF]->(arg:AST)
                where arg_list.type='AST_ARG_LIST'
                with func, params, acall, arg order by arg.childnum
                with func, params, acall, collect(arg) as args

                unwind range(0, size(params)) as i
                //return func.id, acall.id, size(params),size(args)
                match (a) where a.id=params[i].id
                match (b) where b.id=args[i].id
                //return a,b
                //merge (params[i])-[r:REACHES]->(args[i])
                merge (a)<-[r:REACHES]-(b)
                set r.default=False
                set r.type='func_def_call_args_ddg'
                return True as result
        """).single()
    return result.get('result')

def get_all_func_return_ddg_nodes(tx):
    """
    {
      "linenode": [
        [
          30231,
          29188
        ]
      ],
      "func": 30586,
      "retur_node": 30600
    }
    """
    result = tx.run("""
            match (func_decl:AST)-[:EXIT]->(exit:Artificial)<-[:FLOWS_TO]-(last_node:AST)
            where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((func_decl)<-[:CALLS]-()) and last_node.type='AST_RETURN'
            with collect([func_decl, last_node]) as funcs

            unwind funcs as i
            with i[0] as func, i[1] as ln
            match (linenode:AST)-[:PARENT_OF*..4]->(b)-[:CALLS]->(func)
            where exists((linenode)-[:FLOWS_TO]->())
            with func, collect(linenode.id) as acalls, ln
            with {func: func.id, retur_node: ln.id, linenode: acalls} as res
            return collect(res) as result
        """).single()
    return result

def get_ast_prop_nodes(tx):
    """
    {
      "popnode": 48396,
      "var": [
        "lf",
        "email"
      ],
      "props": [
        [
          48396,
          48395,
          "AST_ASSIGN"
        ]
      ]
    }
    """
    result = tx.run("""
            match (a)-[:PARENT_OF]->(b)
            where a.type='AST_PROP' and exists(b.code) and exists(b.classname)
            with collect([a, b.code, b.classname]) as vars

            unwind vars as var
            with var[0] as a, var[1] as code, var[2] as class
            match (a)<-[:PARENT_OF*..5]-(c)
            where a.type='AST_PROP' and exists((c)-[:FLOWS_TO]->())
            with a, collect([a.id, c.id, c.type]) as props, code, class
            with {var: [code, class], props: props, popnode: a.id} as res

            return collect(res) as result
        """).single()
    return result

def add_funccall_cfg(tx):
    result = tx.run("""
            match (func_decl:AST)-[:ENTRY]->(entry:Artificial)
            where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((func_decl)<-[:CALLS]-()) and entry.type='CFG_FUNC_ENTRY'
            with collect([func_decl, entry]) as funcs

            unwind funcs as funci
            with funci[0] as func, funci[1] as entry
            match (b)-[:CALLS]->(func)
            merge (b)-[r:FLOWS_TO]->(entry)
            set r.default=False
            set r.type='linenode_funccall_ddg'
        """).single()
    return True

def add_is_source_prop_to_node(tx):
    result = tx.run("""
            MATCH (a)<-[:PARENT_OF*..10]-(b)
            WHERE a.code in ["_GET", "_POST", "_COOKIE", "_REQUEST", "_ENV", "HTTP_ENV_VARS", "HTTP_POST_VARS", "HTTP_GET_VARS", "_SERVER", "HTTP_SERVER_VARS", "_FILES"] and EXISTS((b)-[:FLOWS_TO]-()) 
            set b.is_source=True
            set a.is_source_child=True
            return count(distinct a) as result
        """).single()
    return result


def get_native_funcs(tx, pids):
    natf = tx.run("""
            match (c)-[:PARENT_OF]->(a)-[:PARENT_OF]->(b)
            where c.type='AST_CALL' and a.type='AST_NAME' and any(flag in a.flags where flag in ['NAME_NOT_FQ'])
            return collect(distinct b.code) as result
        """.format(pids=pids)).single().get('result')

    allf = tx.run("""
            match (func_decl:AST)
            where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] 
            return collect(distinct func_decl.name) as result
        """).single().get('result')

    return [i for i in natf if i not in allf]


def get_node_from_id_cypher(tx, nodeid):
    result = tx.run("MATCH (a) WHERE a.id={nodeid} RETURN a as node".format(nodeid=nodeid))
    result = result.single()
    if result:
        node = result.get('node')
        return node

# TODO: Make this work!! So that we don't need for loop in python
# def set_file_system_paths(tx):
#     result = tx.run("MATCH (a:Filesystem {type: 'File'})-[:FILE_OF]->(f:AST)-[:ENTRY]->(c:Artificial) FOREACH (n IN collect(a, c)| SET n(0).full_name = n(1).name) RETURN true")
#     if result.single():
#         return True
#     return False

def add_fileid_property(driver):

    with driver.session() as session:
        result = session.write_transaction(get_file_ids)
    all_file_ids = list(set(result['ids']))
    all_file_ids.sort()

    for i in range(1, len(all_file_ids)):
        file_id = all_file_ids[i - 1]
        next_file_id = all_file_ids[i]
        print("{}, {}".format(i, file_id), end=" || ")
        if i % 25 == 0:
            print("")

        with driver.session() as session:
            if not session.write_transaction(set_fileid, file_id-1, next_file_id-1, file_id):
                print("FAILED!!!!!!!!!!!!!!!!")
                break

    # For the last file id
    if all_file_ids:
        with driver.session() as session:
            if not session.write_transaction(set_last_fileid, all_file_ids[-1]-1, all_file_ids[-1]):
                print("FAILED!!!!!!!!!!!!!!!!")
        print("{}, {}".format(i, all_file_ids[-1]))

    print("ALL DONE!")

def add_fileid_filename_to_all(driver):

    with driver.session() as session:
        result = session.write_transaction(get_file_ids_names)
        all_file_ids = result['result']

        for i in range(1, len(all_file_ids)):
            file_id = all_file_ids[i - 1][0]
            file_name = all_file_ids[i - 1][1]
            next_file_id = all_file_ids[i][0]
            print("{}, {}".format(i, file_id), end=" || ")
            if i % 25 == 0:
                print("")

            if not session.write_transaction(set_file_id_name, file_id-1, next_file_id-1, file_id, file_name):
                print("FAILED!!!!!!!!!!!!!!!!")
                break

        if not session.write_transaction(set_last_file_id_name, all_file_ids[-1][0]-1, all_file_ids[-1][0], all_file_ids[-1][1]):
            print("FAILED!!!!!!!!!!!!!!!!")
        print("{}, {}".format(i, all_file_ids[-1][0]))

        print("ALL DONE!")

#Given a node A representing the closing location of a <?php ?> element, find the next cfg node B that follows it.
#node A has type NULL and wrong line number. This messes up some things.
def get_next_valid_cfg_node(driver, node, valid_nodes):
    with driver.session() as session:
        result = session.write_transaction(get_next_cfg_node, node)
        for n in result:
            if n.properties["type"] == "NULL":
                get_next_valid_cfg_node(driver, n, valid_nodes)
            elif "lineno" in n.properties or n.properties["type"] == "CFG_FUNC_EXIT":
                valid_nodes.append(n)

def is_not_in(node, list_of_nodes):
    for n in list_of_nodes:
        if n.properties["id"] == node.properties["id"]:
            return False
    return True

def add_flow_edge_from_inside_loops(driver):
    #get all while, for, foreach nodes
    with driver.session() as session:
        loop_nodes = session.write_transaction(get_loop_nodes)
        for loop_node in loop_nodes:
            if loop_node.properties['type'] == 'AST_FOREACH':
                child_1 = session.write_transaction(ithChildren, loop_node, 0)
                back_edge_nodes = session.write_transaction(get_back_edge_nodes, child_1)
                pot_target_nodes = session.write_transaction(get_target_node, child_1)
                #bug in CPG: both true and false cfg edges are labeled with flowLabel: false.
                #Both target nodes are returned when the false branch is followed. The first one is the real false branch target
                #determine the actual target
                targets = []
                for t in pot_target_nodes:
                    if t.properties["type"] == "CFG_FUNC_EXIT":
                        targets.append(t)
                        break
                    elif t.properties["type"] == "NULL": #closure of a <?php ?> tag, must find next FLOWS_TO edge with non null type property.
                        valid_nodes = []
                        get_next_valid_cfg_node(driver, t, valid_nodes)
                        for tr in valid_nodes:
                            targets.append(tr)
                        break
                    elif "lineno" in t.properties:
                        if is_not_in(t, back_edge_nodes):
                            targets.append(t)
                pairs = []
                #pairs = [list(i) for i in itertools.product(back_edge_nodes, target_node)]
                with driver.session() as session:
                    filename = session.write_transaction(get_filename_of_node, back_edge_nodes[0].properties["id"])[0]
                for node in back_edge_nodes:
                    for target_node in targets:
                        if target_node.properties["type"] == "CFG_FUNC_EXIT":
                            print("ADD out_of_loop edges: " + filename + ": " +str( node.properties["lineno"]) +"->"+ "CFG_FUNC_EXIT")
                            pairs.append([node.properties["id"], target_node["id"]])
                        elif "lineno" in node.properties and "lineno" in target_node.properties and node.properties["lineno"] <= target_node.properties["lineno"]:
                            print("ADD out_of_loop edges: " + filename + ": " +str( node.properties["lineno"]) +"->"+ str(target_node["lineno"]))
                            pairs.append([node.properties["lineno"], target_node["lineno"]])
                print("========")
                result = session.write_transaction(add_cfg_pairs, pairs, "cfg_out_of_loop")
                #print(result)
            elif loop_node.properties['type'] == 'AST_WHILE':
                child_1 = session.write_transaction(ithChildren, loop_node, 0)
                back_edge_nodes = session.write_transaction(get_back_edge_nodes, child_1)
                pot_target_nodes = session.write_transaction(get_target_node, child_1)
                #it looks like for while, there is only one outgoing cfg edge with flowLabel False.
                #So pot_target_nodes should always have size equal to 1.
                if len(pot_target_nodes) == 0: #some small parts of code do not have cfg nodes created for them
                    continue
                elif len(pot_target_nodes) > 1:
                    raise Exception("While node has more than one false branches (id: " + str(child_1.properties["id"]))


            #print(loop_node)
            #AST_WHILE, AST_FOREACH: childnum=0 has the flows_to edges

def add_filepath_to_filesystem(driver):

    print("Adding full names to Filesystem nodes...")
    with driver.session() as session:
        result = session.write_transaction(get_file_ids)
    all_file_ids = list(set(result['ids']))
    all_file_ids.sort()
        # print(all_file_ids)

    for i in range(len(all_file_ids)):
        file_id = all_file_ids[i]
        print("{}, {}".format(i, file_id), end=" || ")
        if i%25 == 0 and i != 0:
            print("")

        with driver.session() as session:
            if not session.write_transaction(set_filename, file_id-1):
                print("FAILED!!!!!!!!!!!!!!!!")
                break

    print("ALL DONE!")

def add_class_property_ddg(driver):
    # We will generally fetch these values for all possible class properties
    # Add REACHES edges from each class property definition to the class property usage
    # For example:
    """
        line 30:        messageStack.errors = []
        line 60:        callme(messageStack.errors)
        line 90:        messageStack.errors = old_list

        Add REACHES from both line 30 and 90 to the line 60

        Possible type of parent node of AST_PROP nodes
        ["AST_BINARY_OP", "AST_ASSIGN", "AST_UNARY_OP", "AST_CALL", "AST_ASSIGN_OP", "AST_EXPR_LIST", "AST_ECHO", "AST_RETURN",
        "AST_METHOD_CALL", "AST_UNSET", "AST_ISSET", "AST_EMPTY", "AST_INCLUDE_OR_EVAL", "AST_DIM", "AST_PRE_INC", "AST_POST_INC"]

        Definition type nodes:
        AST_ASSIGN
        AST_ASSIGN_OP   $order->info['tax'] -= tep_calculate_tax($order->info['shipping_cost'], $quotes_array[$default_shipping]['tax']);

        Usage type nodes:
        AST_BINARY_OP
        AST_UNARY_OP, AST_CALL
        AST_DIM     switch ($order->billing['country']['iso_code_3'])  foreach ( $oscTemplate->_data[$this->group] as $group ) 
        AST_PRE_INC     ++$this->_index;
        AST_ECHO
        AST_RETURN
        AST_METHOD_CALL
        AST_UNSET   unset($this->url['query']);
        AST_ISSET
        AST_EMPTY
        AST_INCLUDE_OR_EVAL
        AST_EXPR_LIST    for ($i=0, $n=sizeof($order->products); $i<$n; $i++) {

        First we will find all class property using AST_PROP node. It's child node with property "code" should
        return the value of class name and property name. 


    """

    def_node_types = ['AST_ASSIGN', 'AST_ASSIGN_OP']

    varname = 'errors'
    classname = 'messageStack'
    with driver.session() as session:
        # result = session.write_transaction(get_ast_prop_nodeids, varname, classname)
        result = session.write_transaction(get_ast_prop_nodes)
        all_var_details = result['result']
        var_dict = dict()
        # print(all_var_details)
        for i in all_var_details:
            var_code = i['var'][0]
            var_class = i['var'][1]
            var_name = var_class + "_" + var_code
            if var_name not in var_dict.keys():
                var_dict[var_name] = []
            var_dict[var_name].append(i['props'][0])

        # print(var_dict)
        # exit()
        for all_var_ids in var_dict.values():
            # print(all_var_ids)
            usages = [i[1] for i in all_var_ids if i[2] not in def_node_types]
            defs = [i[1] for i in all_var_ids if i[2] in def_node_types]
            # print(usages, defs)
            # print(all_var_ids)
            ddg_node_pairs = [list(i) for i in itertools.product(defs, usages)]
            # print(ddg_node_pairs)
            # for i in range(1, len(all_var_ids)):
            #     result = session.write_transaction(add_ddg, all_var_ids[0], all_var_ids[i], 'ast_prop_ddg')
            #     if not result:
            #         print("FAILED!!!!!!!!!!!!!!!!")
            #         break
            # for pair in ddg_node_pairs:
            # print(ddg_node_pairs)
            result = session.write_transaction(add_ddg_pairs, ddg_node_pairs, 'ast_prop_ddg')
            if not result:
                print("FAILED!!!!!!!!!!!!!!!!")

    print("ALL DONE!")
    """
    #TODO Fixes:

    - Only add edge between nodes in same file
        We hace multiple classes with same name but in different file, and our current version
        treats them all same and adds edges between its attributes. However, these extra edges
        should not affect finding the exploit, it will only increase false positives for next step.
    """


def add_reaches_to_func_def_call_faster(driver):
    with driver.session() as session:
        result = session.write_transaction(create_all_func_call_defs_args)
    print("ALL DONE!")

def add_reaches_to_func_def_call(driver):
    """
    1. Get the number of function definition in the application, get all nodes with their names and ids
    2. Get each node arguments where this function is called for each function
    3. Add REACHES relationship

    Adds for both class methods and functions


    match (a) match (b)
    where a.id= and b.id=
    merge (a)-[:REACHES]->(b)

    # Get all function definitions
    # match (a:AST)
    # where a.type in ['AST_FUNC_DECL']
    # return collect(distinct a)

    # Get all function call
    # match (a:AST) where a.type in ['AST_CALL'] return count(distinct a)

    # match (a:AST)-[:PARENT_OF]->(b:AST)-[:PARENT_OF]->(func_name:AST) match (func_arg)
    # where a.type in ['AST_CALL'] and b.type in ['AST_NAME'] and func_name.code='converttodb' and func_arg.id=18739
    # match (a:AST)-[:PARENT_OF*]->(c:AST)-[:PARENT_OF]->(arg:AST)
    # where a.type in ['AST_CALL'] and c.type in ['AST_VAR']
    # create (arg)-[:REACHES]->(func_arg)
    # return arg,func_arg
    """
    with driver.session() as session:
        result = session.write_transaction(get_all_func_call_defs_args)
    all_funcs = result['result']
    # print(all_funcs)
    # return
    ddg_node_pairs = {}
    wrong_calls_edges = []
    total = 0

    for func in all_funcs:
        # print(func)
        func_nodeid = func['func']
        func_params = func['params']
        func_calls = func['acalls']
        ddg_node_pairs[func_nodeid] = []

        for func_call in func_calls:
            for param in func_params:
                ddg_node_pairs[func_nodeid].append([func_call, param])
                total += 1

        # for func_call in func_calls:
        #     call_nodeid = func_call['acall']
        #     call_args = func_call['aargs']
        #     # print(call_args)
        #     if len(call_args) > len(func_params):
        #         # print("Something is wrong!!")
        #         # print(call_args, func_params, call_nodeid, func_nodeid)
        #         wrong_calls_edges.append([call_nodeid, func_nodeid])
        #         continue

            # for i in range(len(call_args)):
            #     ddg_node_pairs[func_nodeid].append([call_args[i], func_params[i]])
            #     total += 1

    print("Wrong call edges are: ")
    print(wrong_calls_edges)
    # print(ddg_node_pairs)
    print("Total function definitions to add ddg to: ", len(list(ddg_node_pairs.keys())))        
    print("Total number of DDG pairs adding in applications are: ", total)
    print("Wrong CALLS edges in application: ", len(wrong_calls_edges))
    print("Adding ...")
    print("Function number | Function definition node id | Total number of DDG pairs to add for function")

    i = 0
    temp = 0
    for func in list(ddg_node_pairs.keys()):
        print("{}, {}, {}".format(i, func, len(ddg_node_pairs[func])), end=" || ")
        with driver.session() as session:
            result = session.write_transaction(add_ddg_pairs, ddg_node_pairs[func], 'func_def_call_args_ddg')
        if i%5 == 0 and i != 0:
            print(" --> %{} Complete".format(temp/total*100))
        if not result:
            print("FAILED!!!!!!!!!!!!!!!!")
        i += 1
        temp += len(ddg_node_pairs[func])

    print("ALL DONE!")

def add_reaches_db_query(driver):
    tables = {}
    with driver.session() as session:
        result = session.write_transaction(get_select_statements)
        for select_node in result:
            try:
                select_tables = re.search("(?is)\\b(?:from|into|update)\s+`*(\w+(?:\s*\,\s*\w+)*)`*", select_node['code']).group(1).split(',')
            except Exception as e:
                print("Exception: Can't find table name from query string, skipping the statement")
                f = open("query_exceptions", "a")
                output = "File id: " + str(select_node['fileid']) + ", line #: " +  str(select_node['lineno']) + ", query: " + str(select_node['code']) + "\n"
                f.write(output)
                f.close()
                continue
            for table in select_tables:
                table_list = tables.get(table)
                if table_list:
                    table_list.append(select_node['id'])
                else:
                    tables[table] = [select_node['id']]

        result = session.write_transaction(get_insert_update_statements)
        for insert_node in result:
            try:
                insert_tables = re.search("(?is)\\b(?:from|into|update)\s+`*(\w+(?:\s*\,\s*\w+)*)`*", insert_node['code']).group(1).split(',')
            except Exception as e:
                print("Exception: Can't find table name from query string, skipping the statement")
                f = open("query_exceptions", "a")
                output = "File id: " + str(insert_node['fileid']) + ", line #: " +  str(insert_node['lineno']) + ", query: " + str(insert_node['code']) + "\n"
                f.write(output)
                f.close()
                continue
            for table in insert_tables:
                table_list = tables.get(table)
                if table_list:
                    for select_node in table_list:
                        try:
                            node1 = session.write_transaction(get_father_node, insert_node['id'])
                            node2 = session.write_transaction(get_father_node, select_node)
                            session.write_transaction(add_reaches_edge, node1[0]['id'], node2[0]['id'])
                        except Exception as e:
                            print("Exception occurred while creating a REACHES edge")
                            continue
    print("ALL DONE!")

def get_father_node(tx, node):
    result = tx.run("""
        match (a:AST)<-[:PARENT_OF*..10]-(x:AST) WHERE a.id = {node} AND EXISTS((x)-[:FLOWS_TO]-())
        return collect(distinct x) as result LIMIT 1""".format(node=node)).single()
    if not result:
        return []
    return result.get('result')

def get_select_statements(tx):
    result = tx.run("""
        MATCH (f:AST)-[:PARENT_OF]->(n:AST)-[:PARENT_OF]->(c:AST)
        WHERE f.type = 'AST_CALL' AND n.type = 'AST_NAME' AND c.code in ['mysql_query']
        with collect(f) as func_calls
        unwind func_calls as f
        MATCH(f)-[:PARENT_OF*..10]->(b)
        WHERE b.type = 'string' AND b.code=~'(?i)select .*'
        return collect(b) as result""").single()
    if not result:
        return []
    return result.get('result')

def get_insert_update_statements(tx):
    result = tx.run("""
        MATCH (f:AST)-[:PARENT_OF]->(n:AST)-[: PARENT_OF]->(c:AST)
        WHERE f.type = 'AST_CALL' AND n.type = 'AST_NAME' AND c.code in ['mysql_query']
        with collect(f) as func_calls
        unwind func_calls as f
        MATCH(f)-[: PARENT_OF *..10]->(b)
        WHERE b.type = 'string' AND (b.code =~ '(?i)insert .*' OR b.code =~ '(?i)update .*')
        return collect(b) as result""").single()
    if not result:
        return []
    return result.get('result')

def add_function_return_ddg(driver):

    with driver.session() as session:
        result = session.write_transaction(get_all_func_return_ddg_nodes)
        all_funcs = result['result']

    ddg_node_pairs = {}
    total = 0
    # print(all_funcs)

    for func in all_funcs:
        # print(func)
        func_nodeid = func['func']
        return_nodeid = func['retur_node']
        func_calls = func['linenode']
        ddg_node_pairs[func_nodeid] = []

        for func_call in func_calls:
            ddg_node_pairs[func_nodeid].append([return_nodeid, func_call])
            total += 1

    # print(ddg_node_pairs)
    print("Total function definitions to add ddg to: ", len(list(ddg_node_pairs.keys())))
    print("Total number of DDG pairs adding in applications are: ", total)
    print("Adding ...")
    print("Function number | Function definition node id | Total number of DDG pairs to add for function")

    i = 0
    temp = 0
    for func in list(ddg_node_pairs.keys()):
        print("{}, {}, {}".format(i, func, len(ddg_node_pairs[func])), end=" || ")
        with driver.session() as session:
            result = session.write_transaction(add_ddg_pairs, ddg_node_pairs[func], 'func_return_ddg')
        if i%5 == 0 and i != 0:
            print(" --> %{} Complete".format(temp/total*100))
        if not result:
            print("FAILED!!!!!!!!!!!!!!!!")
        i += 1
        temp += len(ddg_node_pairs[func])

    print("ALL DONE!")

def add_function_call_cfg(driver):
    with driver.session() as session:
        result = session.write_transaction(add_funccall_cfg)
    print("ALL DONE!")

def add_is_source_property(driver):
    with driver.session() as session:
        result = session.write_transaction(add_is_source_prop_to_node)['result']
        print("Added property to nodes: ", result)
    print("ALL DONE!")

"""
match (a)-[:PARENT_OF]->(b)
where a.type='AST_NAME' and any(flag in a.flags where flag in ['NAME_NOT_FQ']) 
return collect(distinct b.code)
"""
def safe_node(tx):
    result = tx.run("""
            MATCH (a)-[r:PARENT_OF]->(b)-[p:PARENT_OF]->(c)
            WHERE a.type = 'AST_CALL'""").format().single()
    return result


def add_flag_to_func(tx, funcs):
    result = tx.run("""
            with {funcs} as funcs
            unwind funcs as func
            match (c)-[:PARENT_OF]->(d)-[:PARENT_OF]->(e)
            where e.code=func and c.type='AST_CALL' and d.type='AST_NAME'
            set e.safe=True
            set c.safe=True
            return collect(distinct e) as result
        """.format(funcs=funcs)).single()
    return
    result = tx.run("""
            with {funcs} as funcs
            unwind funcs as func
            match (a)<-[:ENTRY]-(b)<-[:CALLS]-(c)-[:PARENT_OF]->(d)-[:PARENT_OF]->(e)
            where e.code=func and a.type='CFG_FUNC_ENTRY' and b.type in ['AST_FUNC_DECL', 'AST_METHOD'] and c.type='AST_CALL' and d.type='AST_NAME' and exists(e.code)
            set e.safe=True
            set b.safe=True
            return collect(distinct e) as result
        """.format(funcs=funcs)).single()

def flag_native_func(driver, filename):
    # filename = 'ins.json'
    with open(filename) as file:
        data = json.load(file)

    # print(data)
    data = {k: v for k, v in data.items() if v}
    # print(data)
    with driver.session() as session:
        session.write_transaction(add_flag_to_func, list(data.keys()))


def get_param_return_func(tx, funcid):
    result = tx.run("""
            match (a)-[:PARENT_OF]->(c)
            match (b)
            where a.funcid={funcid} and a.type='AST_RETURN' and b.funcid={funcid} and b.type='AST_PARAM' and c.type="AST_VAR"
            return collect(distinct a) as params, collect(distinct b) as returns
        """.format(funcid=funcid)).single()
    if result:
        return result.get('params'), result.get('returns')
    return [], []

def func_def_exist(tx, funcall):
    result = tx.run("""
            match (a)
            where a.name='{funcall}' and a.type in ['AST_FUNC_DECL', 'AST_METHOD']
            return a as result
        """.format(funcall=funcall)).single()
    if result:
        return True if result.get('result') else False

def count_source_sink_total_pahts(pairs):
    total_pairs = 0
    total_paths = 0
    for sink, source in pairs:
        total_pairs += 1
        if sink == source:
            total_paths += 1
        else:
            with driver.session() as session:
                source_to_sink = session.write_transaction(source_to_sink_data, sink, source)
            # print(sink, source, source_to_sink)
            total_paths += source_to_sink

    print("Total pairs: ", total_pairs)
    print("Total paths from sink-source", total_paths)

def get_satpath_func_calls(driver, filename):
    # filename = 'satpaths/osticket_satpaths_all.json'
    pairs = []
    with open(filename) as file:
        data = json.load(file)
    for p in data:
        if [p[0][-1], p[0][0]] not in pairs:
            pairs.append([p[0][-1], p[0][0]])
        # if [p[-1], p[0]] not in pairs:
        #     pairs.append([p[-1], p[0]])

    all_fcalls = {}
    all_fcalls_ls = []
    native_funcs = []

    with open('ins.json') as file:
        data = json.load(file)

    for pair in pairs:
        # print("pair: ", pair)
        if pair[0] == pair[1]:
            with driver.session() as session:
                node = session.write_transaction(get_node_from_id_cypher, pair[0])
                # print(node['id'], node['lineno'], node['fileid'])
                fcalls = session.write_transaction(get_func_calls_node_all, node['lineno'], node['fileid'])

            if fcalls:
                fcalls = fcalls.get('result')
                all_fcalls["{}_{}".format(pair[0], pair[1])] = fcalls
                for fcall in fcalls:
                    if fcall not in data:
                        with driver.session() as session:
                            if not session.write_transaction(func_def_exist, fcall):
                                native_funcs.append(fcall)
                            else:
                                all_fcalls_ls.append(fcall)

        else:
            with driver.session() as session:
                ddg_paths = session.write_transaction(get_ddg_paths, pair[0], pair[1])

            for path in ddg_paths:
                safe = False
                for node in path.nodes:
                    with driver.session() as session:
                        fcalls = session.write_transaction(get_func_calls_node_all, node['lineno'], node['fileid'])
                    if fcalls:
                        fcalls = fcalls.get('result')
                        all_fcalls["{}_{}".format(pair[0], pair[1])] = fcalls
                        for fcall in fcalls:
                            if fcall not in data:
                                with driver.session() as session:
                                    if not session.write_transaction(func_def_exist, fcall):
                                        native_funcs.append(fcall)
                                    else:
                                        all_fcalls_ls.append(fcall)


        # print(all_fcalls)
    print(all_fcalls)
    print(list(set(all_fcalls_ls)))
    print("Native functions: ", list(set(native_funcs)))

def get_mysql_nodes(tx):
    result = tx.run("""
        match (f:AST)-[:PARENT_OF]->(n:AST)-[:PARENT_OF]->(c:AST)
        where f.type='AST_CALL' and n.type='AST_NAME' and c.code in ['mysql_query']
        with collect(f) as func_calls
        unwind func_calls as f
        MATCH (f)<-[:PARENT_OF*..10]-(b) WHERE EXISTS((b)<-[:FLOWS_TO]-()) 
        return collect({func:f, data:b}) as result""").single()
    if not result:
        return []
    return result.get('result')


# def label_mysql_sources(driver):
#     with driver.session() as session:
#         result = session.write_transaction(get_mysql_nodes)
#     for fcall, data in result.items():
#         print(data)
#     # possible REACHES edges nodes: ["AST_ASSIGN", "AST_UNARY_OP"]



def is_ddg_exploitable_node(sinkid):
    qi = CPGQueryInterface()
    node = qi.run_cypher_query(get_node_from_id_cypher, sinkid)
    fcalls = qi.run_cypher_query(get_func_calls_node, node['lineno'], node['fileid'])
    # with driver.session() as session:
    #     node = session.write_transaction(get_node_from_id_cypher, sinkid)
    #     fcalls = session.write_transaction(get_func_calls_node, node['lineno'], node['fileid'])
    #         # afcalls = session.write_transaction(get_func_calls_node_all, node['lineno'], node['fileid'])
    # # print(fcalls)
    if fcalls:
        fcalls = fcalls.get('result')
        if fcalls:
            # print("safe function calls for node : ", node['id'])
            return False
    return True

def is_ddg_exploitable(sinkid, sourceid):
    qi = CPGQueryInterface()
    ddg_paths = qi.run_cypher_query(get_ddg_paths, sinkid, sourceid)
    # with driver.session() as session:
    #     ddg_paths = session.write_transaction(get_ddg_paths, sinkid, sourceid)

    # print("Total ddg paths: ", len(ddg_paths))
    for path in ddg_paths:
        safe = False
        # print("nodes: ", [node['id']  for node in path.nodes])
        for node in path.nodes:
            # print("processing node: ", node['id'])
            fcalls = qi.run_cypher_query(get_func_calls_node, node['lineno'], node['fileid'])
            # with driver.session() as session:
            #     fcalls = session.write_transaction(get_func_calls_node, node['lineno'], node['fileid'])
            #     # afcalls = session.write_transaction(get_func_calls_node_all, node['lineno'], node['fileid'])
            # print(fcalls)
            if fcalls:
                fcalls = fcalls.get('result')
                if fcalls:
                    # print(fcalls)
                    print("safe function calls for node : ", node['id'], fcalls)
                    safe = True
                    break
        if not safe:
            # print(path)
            return True
    return False

def mark_safe_prop(tx, funcid, safe):
    result = tx.run("""
            match (a)<-[:ENTRY]-(b)<-[:CALLS]-(c)-[:PARENT_OF]->(d)-[:PARENT_OF]->(e)
            where a.funcid={funcid} and a.type='CFG_FUNC_ENTRY' and b.type in ['AST_FUNC_DECL', 'AST_METHOD'] and c.type='AST_CALL' and d.type='AST_NAME' and exists(e.code)
            set e.safe={safe}
            set b.safe={safe}
            return collect(distinct e) as result
        """.format(funcid=funcid, safe=safe))
    return True

def flag_user_func(driver, funcid):
    with driver.session() as session:
        params, returns = session.write_transaction(get_param_return_func, funcid)

    for pair in itertools.product(returns, params):
        if is_ddg_exploitable(driver, pair[0], pair[1]):
            with driver.session() as session:
                session.write_transaction(mark_safe_prop, funcid, safe=False)
            return

    session.write_transaction(mark_safe_prop, funcid, safe=True)
    return

def flag_user_functions(driver):
    funcids = []
    for funcid in funcids:
        flag_user_func(driver, funcid)

def process_satpaths(driver, filename):
    # filename = 'cephoenix_satpaths_2.json'
    pairs = []
    pairs_d = {}
    with open(filename) as file:
        data = json.load(file)
    for p in data:
        pair = p[0]
        if [p[0][-1], p[0][0]] not in pairs:
            pairs.append([p[0][-1], p[0][0]])
            pairs_d["{}_{}".format(pair[-1], pair[0])] = 1
        else:
            pairs_d["{}_{}".format(pair[-1], pair[0])] += 1

    # return pairs
    all_fcalls = {}
    unsafe = 0
    safe = 0
    safep = 0
    unsafep = 0

    for pair in pairs:
        # print("pair : ", pair[0], pair[1])
        if pair[0] == pair[1]:
            exploitable = is_ddg_exploitable_node(driver, pair[0])
        else:
            exploitable = is_ddg_exploitable(driver, pair[0], pair[1])

        if exploitable:
            all_fcalls["{}_{}".format(pair[0], pair[1])] = "Exploitable"
            unsafe += pairs_d["{}_{}".format(pair[0], pair[1])]
            unsafep += 1
        else:
            all_fcalls["{}_{}".format(pair[0], pair[1])] = "Not"
            safe += pairs_d["{}_{}".format(pair[0], pair[1])]
            safep += 1

    # print(all_fcalls)
    # print(pairs_d)
    print("Safe pairs: ", safep)
    print("Unsafe pairs: ", unsafep)
    print("Total pairs: ", safep + unsafep)
    print("Safe paths: ", safe)
    print("Unsafe paths: ", unsafe)
    print("Total paths: ", len(data))
    return pairs
    # return result

def get_all_smarty_assign_nodes(tx):
    result = tx.run("""
            match (a)-[:PARENT_OF]->(b)-[:PARENT_OF]->(c)
            where a.type='AST_METHOD_CALL' and c.code='smarty'
            match (a)-[:PARENT_OF]->(x)
            where x.code='assign'
            return collect(distinct a) as result
        """).single().get('result')

    return result

def prestashop_paths(tx, sinkid, sourceid):
    result = tx.run("""
            MATCH sspath=(source)<-[:ENTRY]-(a:AST)-[:PARENT_OF*..100]->(sink)
            where sink.id={sinkid} and source.id={sourceid}
            with count(distinct sspath) as source_to_sink
            RETURN source_to_sink as source_to_sink
        """.format(sinkid=sinkid, sourceid=sourceid)).single()
    return result.get('source_to_sink')

def prestashop_assign_count(driver):
    total_paths = 0
    with driver.session() as session:
        nodes = session.write_transaction(get_all_smarty_assign_nodes)
        # print(len(nodes))
        for sink in nodes:
            with driver.session() as session:
                entry_nodeid = session.write_transaction(get_file_entry_node, sink['id'])
                paths = session.write_transaction(prestashop_paths, sink['id'], entry_nodeid)
            total_paths += paths
            print("Node id: {}, Entry id: {}, paths: {}, total_paths: {}".format(sink['id'], entry_nodeid, paths, total_paths))
            # print("total_paths: ", total_paths)

# prestashop_assign_count(driver)
# exit()

def get_all_files(tx):
    result = tx.run("MATCH (a:Filesystem) WHERE a.type='File' RETURN collect(distinct a.full_name) as files")
    return result.single().get('files')

def count_file_to_sink_for_all(driver):
    # filepath = sys.argv[1]
    # all_php_files = get_all_php_files(filepath)
    with driver.session() as session:
        all_php_files = session.write_transaction(get_all_files)
    total_files = len(all_php_files)
    source_sinks = dict()
    analysed_files = 0
    total_sinks = 0
    total_paths = 0
    qi = CPGQueryInterface()

    for filename in all_php_files:
        analysed_files += 1
        print("File: ", analysed_files, " out of ", total_files, " ", filename)
        all_sinks = get_sinks(qi, filename)
        total_sinks += len(all_sinks)
        for sinkid in all_sinks:
            with driver.session() as session:
                entry_nodeid = session.write_transaction(get_file_entry_node, sinkid)
                paths = session.write_transaction(file_to_sink_data, sinkid, entry_nodeid)
            total_paths += paths
            print("Node id: {}, Entry id: {}, paths: {}, total_paths: {}".format(sinkid, entry_nodeid, paths, total_paths))
        print("total_paths: ", total_paths)

    print("Total sinks: ", total_sinks)
    print("Total paths: ", total_paths)


def label_static_db_calls(tx, db_functions):
    result = tx.run(f"""
            match (a)<-[:PARENT_OF*..5]-(b)
            where a.code in {db_functions} and b.type='AST_CALL'
            set a.db = True
            with collect(a) as fsources
            unwind fsources as f
            with f
            where f.fileid <> f.funcid
            return collect(distinct f.funcid) as result
        """).single().get('result')
    return result

def label_db_funcs(tx, db_functions):
    # ids of db_functinos
    result_calls = tx.run(f"""
        match (a)<-[:CALLS]-(b)
        where a.id in {db_functions}
        set a.db = True
        with collect(b) as fsources
        unwind fsources as f
        match (f)
        where f.fileid <> f.funcid
        return collect(distinct f.funcid) as result
    """).single().get('result')

    result_methods = tx.run(f"""
        match (a)
        where a.id in {db_functions} and a.type='AST_METHOD'
        set a.db = True
        return collect(distinct a.name) as result
    """).single().get('result')

    # result = tx.run(f"""
    #         match (a)
    #         where a.id in {db_functions}
    #         set a.db = True
    #         with collect(a) as sources
    #         unwind sources as s
    #         match (s)<-[:CALLS]-(b)
    #         where b.fileid <> b.funcid
    #         with collect(distinct b.funcid) as result_calls, sources
    #         unwind sources as s
    #         match (s)
    #         where s.type='AST_METHOD"
            
    #     """).single().get('result')
    return result_calls, result_methods

def label_db_methods(tx, db_methods):
    # name of methods
    result = tx.run(f"""
        match (a)<-[:PARENT_OF]-(b)
        where a.code in {db_methods} and b.type='AST_METHOD_CALL'
        set a.db = True
    """).single()

    return result

def set_db_parent_prop(tx):
    result = tx.run("""
        match (a)<-[:PARENT_OF*0..5]-(b)
        where a.db=True and EXISTS((b)-[:FLOWS_TO]-())
        set b.db_parent=True
    """).single()


def label_db_functions(driver):
    # 1. Get mysqli_query or mysql_query call
    # 2. Mark those AST_CALL as db=True
    # 3. Check if these function is inside another function definition
    # 4. Go to step 2
    # If fileid and funcid are not same, therefore the statement is inside function
    # Get the function declaration node using funcid
    db_functions = ['mysql_query', 'mysqli_query']
    all_funcs = []
    all_methods = []
    #TODO: Check if this works with class methods as well
    with driver.session() as session:
        funcs = session.write_transaction(label_static_db_calls, db_functions)
        while funcs:
            all_funcs.extend(funcs)
            funcs, methods = session.write_transaction(label_db_funcs, funcs)
            print(funcs, methods)
            funcs = [f for f in funcs if f not in all_funcs]
            all_methods.extend(methods)

        methods = list(set(all_methods))
        print(methods)
        session.write_transaction(label_db_methods, methods)

def label_db_parent_nodes(driver):
    with driver.session() as session:
        session.write_transaction(set_db_parent_prop)


# count_file_to_sink_for_all(driver)
# exit()
# filename = 'satpaths/dokan_satpaths_all.json'
# filename = 'satpaths/easy_digital_downlaods_satpaths_all.json'
# filename = 'satpaths/hmsp_satpaths.json'
# filename = 'satpaths/codeigniter_satpaths.json'
# filename = 'satpaths/prestashop_satpaths.json'
# filename = 'satpaths/thirtybees_satpaths.json'
# filename = 'satpaths/phamm_satpaths.json'
# filename = 'satpaths/woocommerce_satpaths.json'
# filename = 'satpaths/zoneminder_satpaths.json'
# filename = 'satpaths/gshopping_satpaths.json'
# filename = 'satpaths/vfront_satpaths.json'

# filename = 'cfgpaths/dokan_cfgpath_model.json'
# filename = 'cfgpaths/thirtybees_cfgpath_model.json'
# filename = 'cfgpaths/osticket.json'
# filename = 'cfgpaths/cephoenix.json'
# filename = 'cfgpaths/collabtive.json'
# filename = 'cfgpaths/easy_dig_dow.json'
# filename = 'cfgpaths/vfront.json'
# filename = 'cfgpaths/gshopping.json'
# filename = 'cfgpaths/zoneminder.json'
# filename = 'cfgpaths/codeigniter.json'
# filename = 'cfgpaths/woocommerce.json'
# filename = 'cfgpaths/prestashop.json'
# filename = 'cfgpaths/phamm.json'
# filename = 'cfgpaths/thirtybees.json'
# filename = 'cfgpaths/hmsp.json'

# get_satpath_func_calls(driver, filename)
# exit()
# flag_native_func(driver, 'ins.json')
# exit()
# pairs = process_satpaths(driver, filename)
# count_source_sink_total_pahts(pairs)
# exit()

def first_required_scripts(driver):
    print("Adding full_name property to Filesystem nodes...")
    add_filepath_to_filesystem(driver)
    print("Adding fileid property to nodes...")
    add_fileid_property(driver)

    with driver.session() as session:
        print("Removing self loops...")
        result = session.write_transaction(remove_self_rels)
        print("Creating indexes...")
        try:
            result = session.write_transaction(create_index)
        except:
            print("Indexes already exists!")
            pass
    print("All required functions Done Successfully!")

def delete_existing_edges(driver):
    with driver.session() as session:
        session.write_transaction(remove_edges, 'ast_prop_ddg')
        session.write_transaction(remove_edges, 'func_def_call_args_ddg')

def add_correct_edges_v2(driver):
    delete_existing_edges(driver)
    print("Adding REACHES edges between argument and parameters -> function definition and function calls...")
    add_reaches_to_func_def_call(driver)
    print(datetime.now())
    print("Adding REACHES edges between class properties...")
    add_class_property_ddg(driver)


if __name__ == '__main__':
    # print(flag_funcs(driver))


    driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
    with driver.session() as session:
        paths = session.write_transaction(get_flows_to_path_adv, 996, 974)
        for path in paths:
            for node in path:
                print(node.properties["lineno"])
            print("=======")
    #add_flow_edge_from_inside_loops(driver)
    #is_ddg_exploitable(driver, 163086, 163076)
    #is_ddg_exploitable(driver, 163160, 163076)
    exit()
    # label_db_functions(driver)
    # exit()
    # first_required_scripts(driver)
    # exit()

    # add_correct_edges_v2(driver)
    # exit()
    print("Adding all other DDG's accross files(only required for backtrack analysis; exit if not required)")
    print("Adding is_source property to nodes")
    # add_is_source_property(driver)
    print(datetime.now())
    print("Adding REACHES edges between argument and parameters -> function definition and function calls...")
    add_reaches_to_func_def_call(driver)
    exit()
    print(datetime.now())
    print("Adding REACHES edges between class properties...")
    # add_class_property_ddg(driver)
    print("Adding REACHES edges in function return statements...")
    # add_function_return_ddg(driver)

    print("Adding FLOWS_TO edges between function call and function definition")
    # add_function_call_cfg(driver)
    # add_fileid_filename_to_all(driver)

    ## Version 4
    # Changing the is_source -> is_source_child for child nodes.
    # Probably affect the old demo scripts.

