
# TODO: Add decorator so that we don't need to add None condition explicity in each function
import logging
logging.basicConfig(level=logging.ERROR)

class Properties(dict):
    def __getitem__(self, name):
        try:
            return super(Properties, self).__getitem__(name)
        except:
            # Because the gremlin version expects to return 'null' if the property do not exist
            # we don't want the program to throw an error
            return "null"

class GremlinNode:
    def __init__(self):
        self.properties = Properties()

    def __getitem__(self, item):
        return self.properties[item]


def convert_cnode_to_gnode(cnode):
    gnode = GremlinNode()
    properties = cnode.items()
    for key, value in properties:
        gnode.properties[key] = value
    return gnode

def get_node_file_line(tx, filename, line, timed = False):
    print(filename, line)
    result = tx.run(f"""
        match (f:Filesystem)
        where f.full_name='{filename}'
        match (a)
        where a.fileid=f.fileid and a.lineno={line} and EXISTS((a)-[:FLOWS_TO]-())
        return a as result
    """)
    values = result.single()
    result_summary = result.consume()
    if values:
        node = convert_cnode_to_gnode(values.get('result'))
        return (node, result_summary) if timed else node
    return (None, result_summary) if timed else None

def get_node_from_id(tx, nodeid, timed=False):
    # 1:1
    # We are expecting to return only single node from this query, because the node ID is unique
    # TODO: Convert the cypher node to the gremlin node
    result = tx.run("MATCH (a) WHERE a.id={nodeid} RETURN a as node".format(nodeid=nodeid))

    values = result.single()
    result_summary = result.consume()
    if values:
        node = convert_cnode_to_gnode(values.get('node'))
        return (node, result_summary) if timed else node
    return (None, result_summary) if timed else None

def check_file_exists(tx, filename, timed=False):
    result = tx.run("""
            match (a:Filesystem)
            where a.full_name="{filename}"
            return a as result
        """.format(filename=filename))
    result_summary = result.summary()
    result = True if result.single() else False
    return (result) if timed else result

def get_all_fileids(tx, timed=False):
    # 2:2
    result = tx.run("MATCH (a:Filesystem) WHERE a.type='File' RETURN collect(a.id) as fileids")
    values = result.single()
    result_summary = result.consume()
    if values:
        fileids = values.get('fileids')
        return (fileids, result_summary) if timed else fileids
    return (None, result_summary) if timed else None

def get_node_calls(tx, nodeid):
    # 8:3
    result = tx.run("MATCH (a:AST)-[:CALLS]->(b:AST) WHERE a.id={node_id} RETURN collect(b) as result".format(node_id=nodeid)).single()
    if result:
        return result.get('result')
    return None

def get_fileid_from_name(tx, filename, timed=False):
    # 10:4
    result = tx.run("MATCH (f:Filesystem) WHERE f.name='{filename}' RETURN collect(f.fileid) as result".format(filename=filename))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_filenode_from_name(tx, filename, timed=False):
    # 10:4
    result = tx.run("MATCH (a) WHERE a.name='{filename}' RETURN collect(a.id) as result".format(filename=filename))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_linenos_of_node(tx, nodeid, timed=False):
    # 13:5
    result = tx.run("MATCH (a:AST) WHERE a.id={nodeid} RETURN [a.lineno, a.endlineno] as result".format(nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        linenos = result1.get('result')
        return (linenos, result_summary) if timed else linenos
    return ([], result_summary) if timed else []

def get_ast_class_id(tx, startid, endid, timed=False):
    # 14:6
    result = tx.run("MATCH (a:AST) WHERE a.id>={startid} and a.id<{endid} and a.type='AST_CALL' RETURN collect(a.id) as result".format(
        startid=startid, endid=endid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_filepath(tx, class_name, timed=False):
    # 16:7
    result = tx.run("MATCH (a:AST)<-[:FLOWS_TO]-(b) WHERE a.name='{class_name}' and a.type='AST_CLASS' RETURN b.name as result".format(
        class_name=class_name))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        path = result1.get('result')
        return (path, result_summary) if timed else path
    return (None, result_summary) if timed else None

def get_endids(tx, endline, startid, endid):
    # 17:8
    result = tx.run("MATCH (a) WHERE a.lineno={endline} and a.id>{startid} and a.id<{endid} RETURN collect(a) as result".format(startid=startid,
        endid=endid, endline=endline)).single()
    if result:
        return result.get('result')
    return None

def get_ast_echo_print_id(tx, startid, endid, timed=False):
    # 18:9
    result = tx.run("MATCH (a) WHERE a.id>={startid} and a.id<{endid} and a.type in ['AST_ECHO', 'AST_PRINT'] RETURN collect(a.id) as result".format(
        startid=startid, endid=endid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_echo_print_functions(tx):
    """
        match (func_decl:AST)-[:ENTRY]->(entry:Artificial {type: 'CFG_FUNC_ENTRY'})
        where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((entry)-[:FLOWS_TO*..30]->(:AST {type: 'AST_ECHO'}))
        match (func_decl)-[:PARENT_OF]->(param:AST {type: 'AST_PARAM_LIST'})
        where exists((param)-[:PARENT_OF]->( {type: 'AST_PARAM'}))
        return collect(distinct func_decl.name) as result

        match (func_decl:AST)-[:ENTRY]->(entry:Artificial {type: 'CFG_FUNC_ENTRY'})
        where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and (exists((entry)-[:FLOWS_TO*..40]->(:AST {type: 'AST_ECHO'})) or exists((entry)-[:FLOWS_TO*..40]->(:AST {type: 'AST_PRINT'})))
        match (func_decl)-[:PREANT_OF]->(param: {type: 'AST_PARAM_LIST})
        where param.childnum>0
        return collect(distinct func_decl.name) as result

    """
    result = tx.run("""
        match (func_decl:AST)-[:ENTRY]->(entry:Artificial {type: 'CFG_FUNC_ENTRY'})
        where func_decl.type in ['AST_FUNC_DECL', 'AST_METHOD'] and exists((entry)-[:FLOWS_TO*..30]->(:AST {type: 'AST_ECHO'}))
        match (func_decl)-[:PARENT_OF]->(param:AST {type: 'AST_PARAM_LIST'})-[:PARENT_OF]->(p:AST {type: 'AST_PARAM'})
        return collect(distinct func_decl.name) as result
    """).single()
    return result.get('result')

dokan_func = ["dokan_seller_meta_box", "display_recommended_item", "shop_order_custom_columns", "seller_meta_box_content", "dokan_admin_report", "add_meta_fields", "display_service_item", "form", "widget", "dokan_content_nav", "render_shortcode", "dokan_page_navi", "dokan_store_category_menu", "dokan_vendor_quick_edit_data", "dokan_withdraw_method_paypal", "dokan_withdraw_method_skrill", "dokan_withdraw_method_bank", "dokan_sales_overview_chart_data", "in_plugin_update_message", "dokan_post_input_box", "dokan_country_dropdown", "dokan_state_dropdown", "dokan_product_listing_filter_months_dropdown", "dokan_privacy_policy_text", "calculate_gateway_fee", "get_readable_rating", "restore_reduced_order_stock"]
codeigniter_func = ["show_404", "show_exception", "get_config", "show_error",
"generate_json","csv_from_result", "xml_from_result","_display","set_status_header", 
"add_field", "create_table", "rename_table", "show_php_error", "load","setError","render", "set_response","setFrom","load_file","viewPost",
"templateCss", "templateJs", "templateCssImage","viewProduct","setBankAccountSettings", "setSeoPageTranslations","setAdminUser", "setBrand",
"setLanguage", "setHistory", "deleteShopCategorie", "setShopCategorie", "setEditPageTranslations", "deleteAdminUser"]
collabtive_func = ["assign"]

codeigniter_func = ['_display', 'show_error', 'set_status_header', 'show_php_error', 'render',
"set_response",'rename_table']
mybloggie_sink_func = ['mysql_query', 'error', 'message', 'sql_query', 'assign_var', 'assign_vars', 'assign_block_vars', 'assign_var_from_handle']


def get_ast_echo_print_id_adv(tx, fileid, lineno=None, sink_func=None, timed=False):
    # 18:9
    # sink_func = ['mysql_query', 'error', 'message', 'sql_query', 'assign_var', 'assign_vars', 'assign_block_vars', 'assign_var_from_handle']
    if sink_func:
        # print("sink functions...")
        result = tx.run("""match (a:AST)-[:PARENT_OF*..2]->(b:AST)
        WHERE a.fileid={fileid} and a.type in ['AST_CALL', 'AST_METHOD_CALL'] and  
        b.code in {sink_func}
        with collect(a) as funcs
        unwind funcs as a
        match (a)<-[:PARENT_OF*0..10]-(x)
        where EXISTS((x)-[:FLOWS_TO]-())
        RETURN collect(distinct x.id) as result""".format(sink_func=sink_func, fileid=fileid))
    elif lineno:
        result = tx.run("MATCH (a) WHERE a.fileid={fileid} and a.type in ['AST_ECHO', 'AST_PRINT'] and a.lineno={lineno} RETURN collect(distinct a.id) as result".format(
            fileid=fileid, lineno=lineno))    
    else:
        result = tx.run("MATCH (a) WHERE a.fileid={fileid} and a.type in ['AST_ECHO', 'AST_PRINT'] RETURN collect(distinct a.id) as result".format(
            fileid=fileid))    
        # if sink_func:
        # else:
        #     result = tx.run("MATCH (f:Filesystem) where f.full_name='{filename}' MATCH (a) WHERE a.fileid=f.fileid and a.type in ['AST_ECHO', 'AST_PRINT'] RETURN collect(distinct a.id) as result".format(
        #         filename=filename))
        # result = tx.run("""
        # MATCH (f:Filesystem) where f.full_name='{filename}' MATCH (a)-[:CALLS]->(b) 
        # WHERE a.fileid=f.fileid and a.type in ['AST_CALL', 'AST_METHOD_CALL'] and b.type in ['AST_FUNC_DECL', 'AST_METHOD'] and 
        # b.name in {app_func} RETURN collect(distinct a.id) as result
        # """.format(filename=filename, app_func=collabtive_func))


    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_ast_func_call(tx, filename, func_name, timed=False):
    result = tx.run(
        "MATCH (f:Filesystem) where f.full_name='{filename}' "
        "MATCH (a)-[:PARENT_OF]->(b)-[:PARENT_OF]->(c) "
        "WHERE a.fileid=f.fileid and a.type = 'AST_CALL' and b.type = 'AST_NAME' and c.code ='{func_name}' "
        "RETURN collect(distinct a.id) as result".format(
            filename=filename, func_name=func_name))

    result1 = result.single()
    result_summary = result.consume()
    if result:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_ast_call_calls_id(tx, nodeid, timed=False):
    # 20:10
    result = tx.run("MATCH (a)-[]->(b)-[:CALLS]->(c) WHERE a.id={nodeid} and b.type='AST_CALL' RETURN collect(a.id) as result".format(
        nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_lineno_in_id_range(tx, startline, startid, endid):
    # 24:11
    result = tx.run("MATCH (a)-[:FLOWS_TO]->() WHERE a.id>={startid} and a.id<{endid} and a.lineno>={startline} RETURN collect(distinct a) as result".format(
        startid=startid, endid=endid, startline=startline)).single()
    if result:
        return result.get('result')

def get_parent_of_node(tx, nodeid):
    result = tx.run(
        "MATCH (a)<-[:PARENT_OF]-(b) WHERE a.id = {nodeid} RETURN b as result".format(
            nodeid=nodeid)).single()
    if result:
        return convert_cnode_to_gnode(result.get('result'))

def get_last_parent_of_path(tx, nodeid, timed=False):
    # 25:12
    result = tx.run("MATCH path=((a)-[:PARENT_OF*]->(b)) WHERE a.id={nodeid} and NOT EXISTS((b)-[:PARENT_OF]->()) RETURN collect(path) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
        return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_node_to_calls(tx, nodeid, timed=False):
    # 25:12 (B)
    result = tx.run("MATCH (a)-[:CALLS]->(b) WHERE a.id={nodeid} RETURN collect(distinct b) as result".format(nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()

    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []    

def add_reaches_edge(tx, nodeid1, nodeid2, timed=False):
    result = tx.run(
        "match (a:AST) where a.id = {nodeid1} "
        "match (b:AST) where b.id = {nodeid2} "
        "create (a)-[:REACHES]->(b) "
        "return a,b".format(nodeid1=nodeid1, nodeid2=nodeid2))
    return result
    # result_summary = result.summary()
    # result = result.single()
    # if result:
    #     nodes = [convert_cnode_to_gnode(node) for node in result.get('result')]
    #     return (nodes, result_summary) if timed else nodes
    # return ([], result_summary) if timed else []

def get_ast_method_node_of_class(tx, method_name, class_name, timed=False):
    # 28:13
    result = tx.run("MATCH (a) WHERE a.name='{method_name}' and a.classname='{class_name}' and a.type='AST_METHOD' RETURN collect(a.id) as result".format(
        method_name=method_name, class_name=class_name))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []


def get_node_with_code(tx, nodeid, timed=False):
    # 29:14
    result = tx.run("MATCH (a)-[:PARENT_OF*]->(b) WHERE a.id={nodeid} and EXISTS(b.code) RETURN collect([b.id, b.code]) as result".format(
        nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_node_with_no_flows_to(tx, startline, endline, startid, endid):
    # 30:15
    result = tx.run("MATCH (a) WHERE a.id>={startid} and a.id<{endid} and a.lineno>={startline} and a.lineno<{endline} and NOT (a)-[:FLOWS_TO]->() RETURN collect(a.id) as result".format(
        startline=startline, endline=endline, startid=startid, endid=endid)).single()
    if result:
        return result.get('result')

def get_reaches_to_path(tx, nodeid, flag=1, timed=False):
    # 31:16
    result = tx.run("MATCH path=((a)<-[:REACHES*0..30]-(b)) WHERE a.id={nodeid} and NOT EXISTS((b)<-[:REACHES]-()) RETURN collect(path) as result".format(nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_reaches_bt_nodes(tx, sinkid, sourceid, flag=0, timed=False):
    # 31:16
    result = tx.run("""MATCH path=((source)-[:REACHES*0..30]->(sink)) WHERE sink.id={sinkid} and source.id={sourceid}
        with path order by length(path) RETURN collect(distinct path) as result limit 30""".format(sinkid=sinkid, sourceid=sourceid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_reaches_bt_nodes_short(tx, source_lineno, source_fileid,
                                       sink_lineno, sink_fileid, length, flag=0, timed=False):
    result = tx.run("""MATCH path=((source)-[:REACHES*]->(sink)) WHERE sink.lineno={sink_lineno} and sink.fileid = {sink_fileid}
     and source.lineno={source_lineno} and source.fileid = {source_fileid} 
     with path order by length(path) RETURN collect(distinct path) as result""".format(
        sink_lineno=sink_lineno, sink_fileid=sink_fileid, source_lineno=source_lineno, source_fileid=source_fileid, length=length))
    print("Done obtaining query paths")
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

# def get_reaches_bt_nodes_short(tx, sinkid, sourceid, length, flag=0, timed=False):
#     # 31:16
#     result = tx.run("""MATCH path=((source)-[:REACHES*0..{length}]->(sink)) WHERE sink.id={sinkid} and source.id={sourceid}
#         with path order by length(path) RETURN collect(distinct path) as result limit 30""".format(sinkid=sinkid, sourceid=sourceid, length=length))
#     result1 = result.single()
#     # print(result1.get('result'))
#     result_summary = result.consume()
#     if result1:
#         if flag:
#             nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
#             return (nodeids, result_summary) if timed else nodeids
#         else:
#             nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
#             return (nodes, result_summary) if timed else nodes
#     return ([], result_summary) if timed else []

def get_flows_to_path(tx, nodeid, flag=1, timed=False):
    # 32:17
    result = tx.run("""MATCH path=((a)<-[:FLOWS_TO*0..30]-(b)) WHERE a.id={nodeid} 
        and NOT EXISTS((b)<-[:FLOWS_TO]-()) RETURN collect(path) as result""".format(nodeid=nodeid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_instruction_type(tx, filename, lineno):
    result = tx.run("""MATCH (f:Filesystem) 
        WHERE f.full_name = $filename
        MATCH (a:AST)
        WHERE a.lineno = $lineno AND a.fileid=f.fileid AND NOT EXISTS {MATCH (a)<-[PARENT_OF]-(b:AST) WHERE b.lineno = a.lineno}
        RETURN a""", filename=filename, lineno=lineno)
    result = result.single()
    if result:
        return convert_cnode_to_gnode(result[0])
    else:
        return None

def get_flows_to_path_adv(tx, sinkid, sourceid, flag=0, timed=False):
    # 35:18
    result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink) where sink.id={sinkid} and source.id={sourceid} 
                    with path order by length(path) RETURN collect(distinct path) as result limit 30""".format(
        sinkid=sinkid, sourceid=sourceid))
    #result_summary = result.summary()
    result = result.single()
    if result:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result.get('result')]
            return nodeids if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result.get('result')]
            return nodes if timed else nodes
    return [] if timed else []
    if result:
        return [[node['id'] for node in path.nodes] for path in result.get('result')]

def get_ast_param_nodes(tx, startline, endline, startid, endid, timed=False):
    # 36:19
    result = tx.run("MATCH (a) WHERE a.id>{startid} and a.id<{endid} and a.lineno>={startline} and a.lineno<={endline} and a.type='AST_PARAM' RETURN collect(a) as result".format(
        startline=startline, endline=endline, startid=startid, endid=endid))
    #result_summary = result.summary()
    result = result.single()
    if result:
        return result.get('result')
    else:
        return None



def get_all_php_files_query(tx, timed=False):
    result = tx.run("""
        match (f:Filesystem)
        where f.type='File'
        return collect({name:f.full_name,id:f.fileid}) as result
    """)
    result1 = result.single()
    result_summary = result.consume()
    if timed:
        return result1.get('result'), result_summary
    return result1.get('result')

def get_php_file_node_query(tx, filename, timed=False):
    result = tx.run("MATCH (f:Filesystem) WHERE f.full_name='{filename}' AND f.type='File' return f.fileid as result".format(
        filename=filename))

    result1 = result.single()
    result_summary = result.consume()
    if timed:
        return result1.get('result'), result_summary
    return result1.get('result')

def get_php_file_query(tx, filename, timed=False):
    result = tx.run("MATCH (f:Filesystem) WHERE f.full_name='{filename}' AND f.type='File' return collect({{name:f.full_name,id:f.fileid}}) as result".format(
        filename=filename))
    result_summary = result.summary()
    result = result.single()
    if timed:
        return result.get('result'), result_summary
    return result.get('result')

def get_ast_return_nodes(tx, startline, endline, startid, endid, timed=False):
    # 37:20
    result = tx.run("MATCH (a) WHERE a.id>{startid} and a.id<{endid} and a.lineno>={startline} and a.lineno<={endline} and a.type='AST_RETURN' RETURN collect(a) as result".format(
        startline=startline, endline=endline, startid=startid, endid=endid))

    result = result.single()
    if result:
        return result.get('result')

def get_exec_flag_nodes(tx, startline, endline, startid, endid, timed=False):
    # 38:21
    result = tx.run("MATCH (a) WHERE a.id>{startid} and a.id<{endid} and a.lineno>={startline} and a.lineno<={endline} and any(flag in a.flags where flag in ['EXEC_REQUIRE', 'EXEC_REQUIRE_ONCE', 'EXEC_INCLUDE']) RETURN collect(a.id) as result".format(
        startline=startline, endline=endline, startid=startid, endid=endid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_nodes_by_code(tx, fileid, timed=False):
    # 41:22
    result = tx.run("""MATCH (a)<-[:PARENT_OF*]-(b) WHERE a.fileid={fileid} and a.code in ["_GET", "_POST", "_COOKIE", "_REQUEST", "_ENV", "HTTP_ENV_VARS", "HTTP_POST_VARS", "HTTP_GET_VARS", "_SERVER", "HTTP_SERVER_VARS", "_FILES"] and EXISTS((b)-[:FLOWS_TO]-()) and not b.type in ["AST_CALL", "AST_METHOD_CALL", "AST_STATIC_CALL"] RETURN collect(b.id) as result""".format(
        fileid=fileid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

############################

def get_conditional_parent_if(tx, nodeid):

    result = tx.run("""match (a:AST)-[:PARENT_OF*]->(b:AST)
        WHERE a.type in ["AST_IF_ELEM"]
        and b.id=$nodeid
        with collect(a) as funcs
        unwind funcs as a
        match (a)-[:PARENT_OF]->(x)
        where EXISTS((x)-[:FLOWS_TO]-()) 
        and x.childnum = 0 and x.id <> $nodeid
        RETURN collect(distinct x) as result""", nodeid=nodeid)


    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return nodes
    return [], result_summary

def get_conditional_parent_while(tx, nodeid):

    result = tx.run("""match (a:AST)-[:PARENT_OF*]->(b:AST)
        WHERE a.type in ["AST_WHILE"]
        and b.id=$nodeid
        with collect(a) as funcs
        unwind funcs as a
        match (a)-[:PARENT_OF]->(x)
        where EXISTS((x)-[:FLOWS_TO]-()) 
        and x.childnum = 0 and x.id <> $nodeid 
        RETURN collect(distinct x) as result""", nodeid=nodeid)


    result1 = result.single()
    result_summary = result.consume()

    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return nodes
    return [], result_summary

def get_conditional_parent_foreach(tx, nodeid):

    result = tx.run("""match (a:AST)-[:PARENT_OF*]->(b:AST)
        WHERE a.type in ["AST_FOREACH"]
        and b.id=$nodeid
        with collect(a) as funcs
        unwind funcs as a
        match (a)-[:PARENT_OF]->(x)
        where EXISTS((x)-[:FLOWS_TO]-()) 
        and x.childnum = 0 and x.id <> $nodeid 
        RETURN collect(distinct x) as result""", nodeid=nodeid)

    result1= result.single()
    result_summary = result.consume()
    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return nodes
    return [], result_summary


def get_conditional_parent_switch(tx, nodeid):

    result = tx.run("""match (a:AST)-[:PARENT_OF*]->(b:AST)
        WHERE a.type in ["AST_SWITCH"]
        and b.id=$nodeid
        with collect(a) as funcs
        unwind funcs as a
        match (a)-[:PARENT_OF]->(x)
        where EXISTS((x)-[:FLOWS_TO]-()) 
        and x.childnum = 0 and x.id <> $nodeid 
        RETURN collect(distinct x) as result""", nodeid=nodeid)


    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return nodes
    return [], result_summary

def get_reaches_edges_query(tx, nodeid):

    result = tx.run("""match (a:AST)<-[:REACHES]-(b:AST)
        WHERE a.id = $nodeid
        RETURN collect(distinct b) as result""", nodeid=nodeid)


    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodes = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return nodes
    return [], result_summary

def get_path_filter_lines(tx, sinkid, sourceid, source_lines, passing=True, flag=0, timed=False):
    if passing:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink)
            WHERE sink.id=$sinkid AND source.id=$sourceid 
            AND EXISTS {
                MATCH (n:AST) WHERE n.lineno IN $source_lines AND n IN nodes(path)
            }
             WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid, source_lines=source_lines)
    else:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink)
            WHERE sink.id=$sinkid AND source.id=$sourceid 
            AND NOT EXISTS {
                MATCH (n:AST) WHERE n.lineno IN $source_lines AND n IN nodes(path)
            }
             WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid, source_lines=source_lines)

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_path_filter_functions(tx, sinkid, sourceid, functions, passing=True, flag=0, timed=False):
    if passing:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink) 
            WHERE sink.id=$sinkid AND source.id=$sourceid
            AND EXISTS {
                MATCH (n:AST)-[:PARENT_OF*]->(m:AST) WHERE m.code = $functions AND n IN nodes(path)
            } WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid, functions=functions)
    else:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink) 
            WHERE sink.id=$sinkid AND source.id=$sourceid
            AND NOT EXISTS {
                MATCH (n:AST)-[:PARENT_OF*]->(m:AST) WHERE m.code = $functions AND n IN nodes(path)
            } WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid, functions=functions)

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_path_filter_db_queries(tx, sinkid, sourceid, passing=True, flag=0, timed=False):
    if passing:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink) 
            WHERE sink.id=$sinkid AND source.id=$sourceid
            AND EXISTS {
                MATCH (n:AST)-[:PARENT_OF*]->(m:AST) WHERE m.code IN ['mysql_query'] AND n IN nodes(path)
            } WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid)
    else:
        result = tx.run("""MATCH path=(source)-[:FLOWS_TO*..50]->(sink) 
            WHERE sink.id=$sinkid AND source.id=$sourceid
            AND NOT EXISTS {
                MATCH (n:AST)-[:PARENT_OF*]->(m:AST) WHERE m.code IN ['mysql_query'] AND n IN nodes(path)
            } WITH path ORDER BY length(path) RETURN collect(DISTINCT path) AS result LIMIT 30""",
            sinkid=sinkid, sourceid=sourceid)

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        if flag:
            nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
            return (nodeids, result_summary) if timed else nodeids
        else:
            nodes = [[convert_cnode_to_gnode(node) for node in path.nodes] for path in result1.get('result')]
            return (nodes, result_summary) if timed else nodes
    return ([], result_summary) if timed else []

def get_source_db_query(tx, fileid, timed=False):
    result = tx.run("""match (a:AST)-[:PARENT_OF]->(:AST)-[:PARENT_OF]->(b:AST)
        WHERE a.type IN ['AST_CALL', 'AST_METHOD_CALL'] AND b.code IN ['mysql_query'] AND a.fileid = {fileid}
        WITH collect(a) AS funcs
        UNWIND funcs AS a
        MATCH (a)<-[:PARENT_OF*0..10]-(x)
        WHERE EXISTS((x)-[:FLOWS_TO]-())
        RETURN collect(distinct x.id) AS result""".format(fileid=fileid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_source_line(tx, fileid, lineno, timed=False):
    result = tx.run("""MATCH (a:AST)
        WHERE a.lineno = $lineno AND a.fileid = $fileid AND EXISTS((a)-[:FLOWS_TO]-())
        RETURN collect(distinct a.id) AS result""", lineno=lineno, fileid=fileid)

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

#TODO does not work with 'print' at the moment
def get_source_function(tx, fileid, function_name, timed=False):
    result = tx.run("""MATCH (a:AST)-[:PARENT_OF]->(:AST)-[:PARENT_OF]->(b:AST)
        WHERE a.type IN ['AST_CALL', 'AST_METHOD_CALL'] 
        AND b.code = '{function_name}'
        AND a.fileid = {fileid}
        WITH collect(a) AS funcs
        UNWIND funcs AS a
        MATCH (a)<-[:PARENT_OF*0..10]-(x)
        WHERE EXISTS((x)-[:FLOWS_TO]-())
        RETURN collect(distinct x.id) AS result""".format(function_name=function_name, fileid=fileid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_nodes_by_code_adv(tx, fileid, timed=False, source_func=[]):
    # 41:22
    # source_func = ['mysql_query', 'sql_query']
    if source_func:
        result = tx.run("""match (a:AST)-[:PARENT_OF]->(:AST)-[:PARENT_OF]->(b:AST)
        WHERE a.fileid={fileid} and a.type in ['AST_CALL', 'AST_METHOD_CALL'] and
        b.code in {source_func}
        with collect(a) as funcs
        unwind funcs as a
        match (a)<-[:PARENT_OF*0..10]-(x)
        where EXISTS((x)-[:FLOWS_TO]-())
        RETURN collect(distinct x.id) as result""".format(source_func=source_func, fileid=fileid))
    else:
        result = tx.run("""MATCH (a)<-[:PARENT_OF*]-(b) 
        WHERE a.fileid={fileid} and 
        a.code in ["_GET", "_POST", "_COOKIE", "_REQUEST", "_ENV", "HTTP_ENV_VARS",
        "HTTP_POST_VARS", "HTTP_GET_VARS", "_SERVER", "HTTP_SERVER_VARS", "_FILES"] 
        and EXISTS((b)-[:FLOWS_TO]-()) 
        RETURN collect(distinct b.id) as result""".format(fileid=fileid))
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def is_ddg_dependent_interprocedural(tx, sinkid, sourceid, timed=False):
    result = tx.run("MATCH (a) where  a.id={sinkid} match (b) WHERE b.id={sourceid} and EXISTS((b)-[r:REACHES*0..30]->(a)) RETURN true as result".format(
        sinkid=sinkid, sourceid=sourceid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        exists = result1.get('result')
        return (exists, result_summary) if timed else exists
    return (False, result_summary) if timed else False

def is_ddg_dependent(tx, sinkid, sourceid, timed=False): #1111614, 1111600
    #result = tx.run("MATCH (a) where  a.id={sinkid} match (b) WHERE b.id={sourceid} and EXISTS((b)-[:REACHES*0..30]->(a))  RETURN true as result".format(
    #    sinkid=sinkid, sourceid=sourceid)) #this query takes too long if interprocedural REACHES edges are present.
    result = tx.run(
        "MATCH p=((b)-[:REACHES*0..30]->(a)) where  a.id={sinkid} and b.id={sourceid} and all(x in relationships(p) where x.type is null)  RETURN count(*)".format(
            sinkid=sinkid, sourceid=sourceid)) #query rewritten because Cypher does not allow specification of name of relationship inside EXISTS.

    result1 = result.single()[0]
    result_summary = result.consume()
    #if result:
    if result1 > 0:
        #exists = result.get('result')
        return (True, result_summary) if timed else True
    return (False, result_summary) if timed else False

def get_ddg_paths(tx, sinkid, sourceid, timed=False):
    # print(sinkid, sourceid)
    result = tx.run("MATCH path=((a)<-[:REACHES*..50]-(b)) where a.id={sinkid} and b.id={sourceid} RETURN collect(path) as result limit 10".format(
        sinkid=sinkid, sourceid=sourceid))


    result1 = result.single()
    result_summary = result.consume()
    paths = result1.get('result') if result1 else []
    # print("Total ddg paths: ", len(paths))

    return (paths, result_summary) if timed else paths

def is_flows_to_edge_exists(tx, nodeid, timed=False):
    result = tx.run("MATCH (a) where a.id={nodeid} and exists((a)-[:FLOWS_TO]-()) return a".format(nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    return (result1, result_summary) if timed else result1

def get_flows_to_parent_node(tx, nodeid, timed=False):
    result = tx.run("MATCH (a)<-[:PARENT_OF*0..10]-(b) WHERE a.id={nodeid} and EXISTS((b)<-[:FLOWS_TO]-()) RETURN b as result".format(nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        node = result1.get('result')
        return (node, result_summary) if timed else node
    return (None, result_summary) if timed else None

def backtrack_from_sink_node_other_file(tx, nodeid, timed=False):
    result = tx.run("match path=(a)<-[:REACHES*..100]-(b) where a.id={nodeid} and a.fileid<>b.fileid and b.is_source=True return collect(distinct b.id) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        sourceids = result1.get('result')
        return (sourceids, result_summary) if timed else sourceids
    return ([], result_summary) if timed else []

#bug: the is_source attribute is only present in the leaf nodes of the AST subtree of an instruction
#todo db_scripts.py: propagate/apply the is_source to instruction node
#$action = getArrayVal($_GET, "action")
#is_source is only present in the string node "$_GET". It serves no purpose there. It needs to be added to the AST_ASSIGN instead.
def backtrack_from_sink_node(tx, nodeid, timed=False):
    result = tx.run("match path=(a)<-[:REACHES]-(b)-[:PARENT_OF*..10]->(c) where a.id={nodeid} and c.is_source=True return collect(distinct b.id) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        sourceids = result1.get('result')
        return (sourceids, result_summary) if timed else sourceids
    return ([], result_summary) if timed else []

def backtrack_from_sink_node_to_source_paths(tx, nodeid, timed=False):
    result = tx.run("match path=(a)<-[:REACHES*..50]-(b) where a.id={nodeid} and b.is_source=True return collect(path) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        sourceids = result1.get('result')
        return (sourceids, result_summary) if timed else sourceids
    return ([], result_summary) if timed else []

def backtrack_from_sink_node_to_any_node(tx, nodeid, timed=False):
    result = tx.run("match path=(a)<-[:REACHES*..50]-(b) where a.id={nodeid} and not exists((b)<-[:REACHES]-()) and exists((b)<-[:FLOWS_TO]-())  return collect(path) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        sourceids = result1.get('result')
        return (sourceids, result_summary) if timed else sourceids
    return ([], result_summary) if timed else []

def get_ddg_path(tx, nodeid):
    # 42:23
    result = tx.run("MATCH path=(a)-[]->(ast_call:AST)-[:CALLS]->(f_call:AST)-[:ENTRY]->(f_entry:Artificial)-[:REACHES*..100]->(f_exit:Artificial)<-[:EXIT]-() WHERE a.id={nodeid} AND ast_call.type='AST_CALL' RETURN collect(path) as result".format(
        nodeid=nodeid)).single()
    if result:
        return result.get('result')

def get_cfg_paths_btw_nodes(tx, nodeid1, nodeid2, timed=False):
    result = tx.run(
        "MATCH path=(a)-[FLOWS_TO*]->(b) where a.id={nodeid1} and b.id={nodeid2} RETURN collect(path) as result limit 10".format(
            nodeid1=nodeid1, nodeid2=nodeid2))
    #result_summary = result.summary()
    result = result.single()
    paths = result.get('result') if result else []
    return paths if timed else paths

def get_cfg_path(tx, nodeid, timed=False):
    # 43:24
    result = tx.run("MATCH (a)-[]->(ast_call:AST)-[:CALLS]->(f_call:AST)-[:ENTRY]->(f_entry:Artificial) WHERE a.id={nodeid} AND ast_call.type='AST_CALL' MATCH path=(f_entry:Artificial)-[:FLOWS_TO*..100]->(f_exit:Artificial)<-[:EXIT]-() RETURN collect(path) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = [[node['id'] for node in path.nodes] for path in result1.get('result')]
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_all_parameters(tx, nodeid, timed=False):
    # 44:25
    # NOTE: We don't know what it returns, we couldn't find any case to verify the results
    result = tx.run("MATCH path=(a)-[:PARENT_OF]->(b)<-[:PARENT_OF*..20]-(c)-[:PARENT_OF]->(d) WHERE a.id={nodeid} and not b.code IN ['HTTP_GET_VARS', '_GET', 'HTTP_POST_VARS', '_POST'] AND d.type<>'string' RETURN collect(path) as result".format(
        nodeid=nodeid))

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        nodeids = result1.get('result')
        return (nodeids, result_summary) if timed else nodeids
    return ([], result_summary) if timed else []

def get_array_elem_nodes(tx, nodeid, timed=False):
    result = tx.run(f"match(n:AST)-[:PARENT_OF]->(b) where n.id = {nodeid} and b.type='AST_ARRAY_ELEM' return collect(b) as result")

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        res = [convert_cnode_to_gnode(node) for node in result1.get('result')]
        return (res, result_summary) if timed else res
    return []


def get_node_from_line(tx, line, idRange, timed=False):
    result = tx.run(f"MATCH (a) WHERE a.lineno = {line} and a.id >= {idRange[0]} and a.id < {idRange[1]} "
                    "and EXISTS((a)-[:FLOWS_TO]-()) RETURN a as result")

    result1 = result.single()
    result_summary = result.consume()
    if result1:
        res = result1.get('result')
        return (res, result_summary) if timed else res
    return []

def get_node_from_lineno(tx, lineno, filename, timed=False):
    result = tx.run(f"MATCH (f:Filesystem) where f.full_name='{filename}' MATCH (a) WHERE a.lineno = {lineno} and a.fileid = f.fileid "
        "and EXISTS((a)-[:FLOWS_TO]-()) RETURN collect(a) as result")
    result1 = result.single()
    result_summary = result.consume()
    if result1:
        res = result1.get('result')
        return (res, result_summary) if timed else res
    return []

def get_entry_and_exit_nodes(tx, node, timed=False):
    nodeid = node.properties["id"]
    result = tx.run(f"MATCH (b)<-[:EXIT]-(n)-[:ENTRY]->(a) where n.id = {nodeid} RETURN [a,b] as result")
    values = result.single()
    result_summary = result.consume()
    result = [convert_cnode_to_gnode(node) for node in values.get('result')] if values else []
    return (result, result_summary) if timed else result

def get_actual_paths_take_two(tx, nodes, i):
    source_node_id = nodes[0].properties['id']
    dest_node_id = nodes[1].properties['id']
    path_checker = False
    counter = 0
    result = tx.run(
        f"MATCH p=(a{{id:{source_node_id}}})-[r:FLOWS_TO*{i}..{i}]->(c{{id:{dest_node_id}}}) RETURN collect(p) as result"
    ).single().get('result')
    return result

def get_actual_paths(tx, nodes):
    source_node_id = nodes[0].properties['id']
    dest_node_id = nodes[1].properties['id']
    path_checker = False
    counter = 0
    result = tx.run(
        f"MATCH p=(a{{id:{source_node_id}}})-[r:FLOWS_TO*]->(c{{id:{dest_node_id}}}) RETURN collect(p) as result",
        timeout=60
        ).single().get('result')
    return result

def count_cfg_paths_between_nodes_take_two(tx, nodes, i, timed=False):
    source_node_id = nodes[0].properties['id']
    dest_node_id = nodes[1].properties['id']
    # print("the ids are: ", source_node_id, dest_node_id)
    path_checker = False
    counter = 0

    # for k in range(0, 1000):
        # print("k value is: ", k)
    result = tx.run(f"MATCH p=(a{{id:{source_node_id}}})-[:FLOWS_TO*{i}..{i}]->(b{{id:{dest_node_id}}}) RETURN count(p) as result", timeout=120
                    ).single().get('result')

    return result
    # values = result.single()
    # result_summary = result.consume()
    # result = values.get('result') if values else []
    # return (result, result_summary) if timed else result

def count_cfg_paths_between_nodes(tx, nodes, timed=False):
    source_node_id = nodes[0].properties['id']
    dest_node_id = nodes[1].properties['id']
    print("the ids are: ", source_node_id, dest_node_id)
    path_checker = False
    counter = 0


    result = tx.run(f"MATCH p=(a{{id:{source_node_id}}})-[:FLOWS_TO*]->(b{{id:{dest_node_id}}}) RETURN count(p) as result",timeout=120
                    ).single().get('result')
    print("Done running the query...")
    return result
    #
    # cfg_counter = 0
    # temp_node_dict = [source_node_id]
    # node_dict = {source_node_id: 'not_checked'}
    # still_checking = False
    # while temp_node_dict != []:
    #     keys = list(node_dict.keys())
    #     values = list(node_dict.values())
    #     still_checking = False
    #     for i in range(0, len(keys)):
    #         if values[i] == 'not_checked':
    #             still_checking = True
    #             print("Id being sent now is...", keys[i])
    #             result = tx.run(f"MATCH p=(a{{id:{keys[i]}}})-[:FLOWS_TO*1..1]->(b) RETURN collect(b.id) as result", timeout=60).single().get('result')
    #             print("Obtained next node...", result)
    #             node_dict[keys[i]] = result
    #             for b in result:
    #                 if b not in node_dict:
    #                     node_dict[b] = 'not_checked'
    #                 if b == dest_node_id:
    #                     cfg_counter += 1
    #                     node_dict[b] = 'arrived'
    #     if still_checking == False:
    #         # next_node_id = values[i]
    #         # if next_node_id == 'arrived': #all nodes have been checked
    #         temp_node_dict = []
    #
    # return cfg_counter

        # for node, value in node_dict.items():
        #     if value == 'not_checked':
        #         result = tx.run(f"MATCH p=(a{{id:{node}}})-[:FLOWS_TO*1..1]->(b) RETURN collect(b.id) as result", timeout=60).single().get('result')
        #         node_dict[node] = result
        #         for b in result:
        #             if b not in node_dict:
        #                 node_dict[b] = 'not_checked'
        #             if b == dest_node_id:
        #                 cfg_counter += 1
        #                 node_dict[b] = 'arrived'
        #     else:
        #         next_node_id = value
        #         if next_node_id == 'arrived': #all nodes have been checked
        #             temp_node_dict = []

    # for k in range(0, 1000):
    #     print("k value is: ", k)
    #     result = tx.run(f"MATCH p=(a{{id:{source_node_id}}})-[:FLOWS_TO*{k}..{k}]->(b{{id:{dest_node_id}}}) RETURN count(p) as result", timeout=60
    #                     ).single().get('result')
    #     if result > 0:
    #         counter += result
    #         path_checker = True
    #     if result == 0 and path_checker == True:
    #         break
    # return counter
    # values = result.single()
    # result_summary = result.consume()
    # result = values.get('result') if values else []
    # return (result, result_summary) if timed else result

def get_instructions_in_list_of_ids(tx, method_node, list_of_identifiers, timed=False):
    method_id = method_node.properties["id"]
    result = tx.run(f"match (a)<-[FLOWS_TO]-(n)-[PARENT_OF*]->(c) where c.code in {list_of_identifiers} and a.funcid = {method_id} and n.funcid = {method_id} and c.funcid = {method_id} return collect(n) as result")

    result1 = result.single()
    result_summary = result.consume()
    result = [convert_cnode_to_gnode(node) for node in result1.get('result')] if result1 else []
    return (result, result_summary) if timed else result

#checked
def get_nodes_with_code(tx, method_node, list_of_identifiers, timed=False):
    method_id = method_node.properties["id"]
    if 'echo' in list_of_identifiers:
        result1 = tx.run(
            f"match (a:AST) where a.type = 'AST_ECHO' and a.funcid = {method_id}  return collect(a) as result")
        values1 = result1.single()
        result_summary1 = result1.consume()
    result = tx.run(f"match (a:AST) where (a.code in {list_of_identifiers} or a.name in {list_of_identifiers}) and a.funcid = {method_id}  return collect(a) as result")
    values = result.single()
    result_summary = result.consume()
    result = [convert_cnode_to_gnode(node) for node in values.get('result')] if values else []
    result1 = [convert_cnode_to_gnode(node) for node in values1.get('result')] if values1 else []
    for node in result1:
        result.append(node)
    return (result, result_summary) if timed else result

def get_parent_instruction(tx, code_node, timed=False):
    code_node_id = code_node.properties["id"]
    result = tx.run(f"MATCH (n:AST)<-[:PARENT_OF*]-(b) where n.id = {code_node_id} and exists((b)-[:FLOWS_TO]-(:AST)) RETURN b as result order by b.id DESC")
    values = result.single()
    result_summary = result.consume()
    result = convert_cnode_to_gnode(values[0]) if values else []
    return (result, result_summary) if timed else result

def count_cfg_paths_instruction_is_in(tx, sensitive_instruction_nodes, entry_exit_nodes, method_node, timed=False):
    method_id = method_node.properties["id"]
    node_ids = []
    for sensitive_instruction in sensitive_instruction_nodes:
        node_ids.append(sensitive_instruction.properties["id"])
    #instruction_node_id = instruction_node.properties["id"]
    entry_id = entry_exit_nodes[0].properties["id"]
    exit_id = entry_exit_nodes[1].properties["id"]
    print(entry_id, exit_id, node_ids)
    print("calling the query now...")
    #the query below can compute the paths that do NOT have sensitive instructions and we can subtract from number of paths but it is too slow
    #query = f"match p = (a)-[:FLOWS_TO*]->(b)-[:FLOWS_TO*]->(c) where a.id = {entry_id} and not b.id in {node_ids} and c.id = {exit_id} return count(p) as result"
    #query = f"match p = (a)-[r:FLOWS_TO*]->(b)-[q:FLOWS_TO*]->(c) where a.id = {entry_id} and b.id in {node_ids} and c.id = {exit_id} and r.type <> 'linenode_funccall_ddg' and q.type <> 'linenode_funccall_ddg' return count(p) as result"

    path_checker = False
    max_length = -1
    tracker = 1
    print("Figuring out the max length...")
    for i in range(1, 1000):
        # print("We are checking if ", tracker, " is the max length between entry node and exit node...")
        result = tx.run(
            f"""match p = (a{{id:{entry_id}}})-[r:FLOWS_TO*{i}..{i}]->(c{{id:{exit_id}}}) return count(p) as result"""
        ).single().get('result')
        if result > 0:
            path_checker = True
            max_length = i
        if result == 0 and path_checker == True:
            max_length = i
            break
        tracker+=1

    print("Done obtaining the max length. The length of the longest path between the entry node and exit node is ", max_length - 1)
    path_counter = 0
    tracker2 = 1
    tracker = 1

    sub_path_checker = False
    sub_start = -1
    sub_end = -1
    first_half = {}
    for node_id in node_ids:
        print("Obtaining sub max length 1")
        for j in range(0, max_length):
            result = tx.run(
                f"""match p = (a{{id:{entry_id}}})-[r:FLOWS_TO*{j}..{j}]->(b{{id:{node_id}}}) return count(p) as result"""
            ).single().get('result')
            if result > 0:
                sub_path_checker = True
                sub_start = j
            if result == 0 and sub_path_checker == True:
                sub_end = j
                first_half[node_id] = (sub_start, sub_end)
                break

    sub_path_checker = False
    sub_start = -1
    sub_end = -1
    second_half = {}
    for node_id in node_ids:
        print("We are obtaining the max length for the sub paths")
        for j in range(0, max_length):
            result = tx.run(
                f"""match p = (a{{id:{node_id}}})-[r:FLOWS_TO*{j}..{j}]->(b{{id:{exit_id}}}) return count(p) as result"""
            ).single().get('result')
            if result > 0:
                sub_path_checker = True
                sub_start = j
            if result == 0 and sub_path_checker == True:
                sub_end = j
                second_half[node_id] = (sub_start, sub_end)
                break

    path_counter = 0
    for node_id in node_ids:
        first = first_half[node_id]
        second = second_half[node_id]
        for j in range(first[0], first[1]):
            for k in range(second[0], second[1]): #k value is
                if entry_id == 30077 and exit_id == 30078:
                    print("We are obtaining paths of length ", j," and ", k, " between entry node and exit node through sensitive instruction")
                result = tx.run(
                    f"""match p = (a{{id:{entry_id}}})-[r:FLOWS_TO*{j}..{j}]->(b)-[q:FLOWS_TO*{k}..{k}]->(c{{id:{exit_id}}}) where b.id in {node_ids} return count(p) as result"""
                ).single().get('result')
                path_counter = path_counter + result
    tracker2 += 1
    print("Done counting all the paths between entry node and exit node through sensitive instruction")
    return path_counter



    # result = tx.run(
    #     f"""match p = (a)-[r:FLOWS_TO*]->(b)-[q:FLOWS_TO*]->(c) where a.id = {entry_id} and b.id in {node_ids} and c.id = {exit_id} return count(p) as result"""
    # ).single().get('result')
    # return result

    # query = f"match p = (a)-[r:FLOWS_TO*]->(b)-[q:FLOWS_TO*]->(c) where a.id = {entry_id} and b.id in {node_ids} and c.id = {exit_id} return count(p) as result"
    # result = tx.run(query)
    # print("Result is ", result)
    # print("Query terminated 1!")
    # values = result.single()
    # print("Query terminated!")
    # result_summary = result.consume()
    # print("Query terminated twice!")
    # #result1 = tx.run(f"match p = (b)-[:FLOWS_TO*]->(c) where b.id = {instruction_node_id} and c.id = {exit_id} return count(p) as result")
    # #values1 = result1.single()
    # #result_summary = result.consume()
    # result = values.get('result') if values else []
    # return (result, result_summary) if timed else result

def get_filename_of_node(tx, nodeid, timed=False):
    filename = tx.run("MATCH (a) MATCH (f:Filesystem) WHERE a.id={nodeid} AND f.fileid=a.fileid AND f.type in ['File'] RETURN f.full_name as result".format(
        nodeid=nodeid)).single()
    return [filename.get('result'),0] if filename else [None,0]

def get_full_path_from_ids(tx, nodeids, timed=False):
    result = tx.run("MATCH (a) WHERE a.id in {nodeids} RETURN collect(a) as result".format(nodeids=nodeids))
    values = result.single()
    result_summary = result.consume()
    result = [convert_cnode_to_gnode(node) for node in values.get('result')] if values else []
    return (result, result_summary) if timed else result

def get_callee(tx, call_node, timed=False):
    call_node_id = call_node.properties["id"]
    result = tx.run(f"MATCH (a)-[r:CALLS]->(b) WHERE a.id = {call_node_id} RETURN collect(b.id) as result")
    values = result.single()
    result = values.get('result')
    return result
    # result_summary = result.consume()
    # result = [convert_cnode_to_gnode(node) for node in values.get('result')] if values else []
    # return (result, result_summary) if timed else result

def get_loop_nodes(tx, timed=False):
    result = tx.run("MATCH (a) WHERE a.type in ['AST_WHILE', 'AST_FOR', 'AST_FOREACH'] RETURN collect(a) as result")
    values = result.single()
    result_summary = result.consume()
    result = [convert_cnode_to_gnode(node) for node in values.get('result')] if values else []
    return (result, result_summary) if timed else result

def get_subtree_identifiers_and_types(tx, node, timed=False):
    nodeid = node.properties["id"]
    query = "match a"

def extractInfoFromCallSite(tx, nodeid, timed=False):
    logging.debug("extractInfoFromCallSite")
    # Groovy extractInfoFromCallSite in static-helper.groovy
    """
        This function returns
        - lineno of the given node
        - filename of the given node

        - lineno of the (given node -CALLS-> node)
        - filename of the (given node -CALLS-> node)
    """

    info = dict()
    result = tx.run("MATCH (a) MATCH (f:Filesystem) WHERE a.id={nodeid} AND f.fileid=a.fileid and f.type='File' OPTIONAL match (a)-[:CALLS]->(b) RETURN a as current_node,  b as next_node, f as file_node".format(nodeid=nodeid)).single()
    # result_summary = result.summary()
    # result = result.single()
    current_node = result.get('current_node')
    next_calls_node = result.get('next_node')
    current_file_node = result.get('file_node')

    info["filename_callsite"] = current_file_node['full_name']
    info["lineno_callsite"] = current_node['lineno']

    if (next_calls_node):
        result = tx.run("MATCH (f:Filesystem) WHERE f.fileid={fileid} AND f.type='File' RETURN f as file_node".format(fileid=next_calls_node['fileid'])).single()
        file_node = result.get('file_node')
        info["filename_defsite"] = file_node['full_name']
        info["lineno_defsite"] = next_calls_node['lineno']
    else:
        info["filename_defsite"] = None
        info["lineno_defsite"] = None

    return info

def getEnclosingTrueCond(tx, node, timed=False):
    logging.debug("getEnclosingTrueCond")
    # Groovy getEnclosingTrueCond in static-helper.groovy
    # REQUIRES TESTING
    # With while loop, what is statementsEnh doing, why it reset temp to node after if-else
    """
        This function does folllowing:
        - if the line of code is inside any block then do following otherwise return [] list
        - if the code is inside any block find the node which holds the
          condition which needs to be true to execute that line of code

        Steps:
        CP -> PP -> PPP <- CHILD (all PARENT_OF relationship)
        CP: Given node in argument

        - get the PP's
        - if: any of the PP's is childMap type (this condition basically means that CP is AST_STMT_LIST)
          - return the PP
        - else:
          - if the PP type is AST_STMT_LIST then get PPP childMap type nodes
        - Get the last node's ith child according to the childMap dict


        NOTES:
        - The last lines of the function returns an output, first implementation is
        not required. 
        - The temp node is returned implicitely (which I don't understad how)
        - The node is argument is gremlin type of node, not cypher
    """

    childMap = {
        "AST_IF_ELEM" : 0,
        "AST_WHILE" : 0,
        "AST_FOR" : 1
    }
    # Because the given node in argument is Gremlin type
    nodeid = node.properties['id']
    result_node = []

    PP = tx.run("MATCH (CP)<-[:PARENT_OF]-(PP) WHERE CP.id={nodeid} AND PP.type in {typeList} RETURN PP as result".format(
        nodeid=nodeid, typeList=list(childMap.keys()))).single()

    if PP:
        loop_node = PP.get('result')
    else:
        loop_node = tx.run("MATCH (CP)<-[:PARENT_OF*..2]-(PP)<-[:PARENT_OF]-(PPP) WHERE CP.id={nodeid} AND PP.type in ['AST_STMT_LIST'] and PPP.type in {typeList} RETURN PPP as result".format(
        nodeid=nodeid, typeList=list(childMap.keys()))).single()
        loop_node = loop_node.get('result') if loop_node else []

    if loop_node:
        result_node = tx.run("MATCH (LN)-[:PARENT_OF]->(RN) WHERE LN.id={nodeid} AND RN.childnum={childnum} RETURN collect(RN) as result".format(
            nodeid=loop_node['id'], childnum=childMap[loop_node['type']])).single()

    # FIX: No purpose in returning list of list
    return [[convert_cnode_to_gnode(node) for node in result_node.get('result')]] if result_node else [[]]

def getConditionsFromFalseBranch(tx, node):
    logging.debug("getConditionsFromFalseBranch")
    # CP <- PP <- PPP && RP <- PP
    # where PP.type = 'AST_IF_ELEM' and PPP.type = 'AST_IF' and RP.type != None

    # Because the given node in argument is Gremlin type
    nodeid = node.properties['id']

    result = tx.run("MATCH (CP)<-[:PARENT_OF]-(PP)<-[:PARENT_OF]-(PPP) WHERE CP.id={nodeid} AND PP.type in ['AST_IF_ELEM'] and PPP.type in ['AST_IF'] MATCH (RP)<-[:PARENT_OF]-(PP) WHERE RP.childnum=0 AND EXISTS(RP.type) RETURN collect(RP) as result".format(
        nodeid=nodeid)).single()

    # FIX: No purpose in returning list of list
    return [[convert_cnode_to_gnode(node) for node in result.get('result')]] if result else [[]]

def get_function_call_arguments(tx, node):
    logging.debug("get_function_call_arguments")
    nodeid = node.properties['id']
    result = tx.run(
        "MATCH (CP)-[]->(CHILD)-[]->(RN) WHERE CP.id={nodeid} AND CHILD.type in ['AST_ARG_LIST'] return collect(RN) as result".format(
            nodeid=nodeid)).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def callToArguments(tx, node):
    logging.debug("callToArguments")
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[]->(CHILD)-[]->(RN) WHERE CP.id={nodeid} AND CHILD.type in ['AST_ARG_LIST'] return collect(RN) as result".format(
        nodeid=nodeid)).single()

    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_function_name(tx, node):
    return 1

def get_instruction_subtree(tx, id):
    result = tx.run(
        f"""MATCH p=(a{{id:{id}}})-[r:PARENT_OF]->(b) RETURN b"""
    ).single().get('result')
    return result

def get_all_dataflow_paths(tx, source_lineno, source_fileid, sink_lineno, sink_fileid):
    result = tx.run(
        f"""MATCH p=(a{{is_source:True, lineno: {source_lineno}, fileid: {source_fileid}}})-[r:REACHES*]->(b{{type:"AST_ECHO", lineno:{sink_lineno}, fileid:{sink_fileid}}}) RETURN collect(p) as result"""
    ).single().get('result')
    return result

def get_other_subtrees(tx, lineno, fileid):
    result = tx.run(
        f"""MATCH p=(a)-[r:PARENT_OF]->(b) where a.lineno <> {lineno} and a.fileid <> {fileid} RETURN b"""
    ).single().get('result')
    return result

def get_ancestor_nodes(tx, fileid, lineno):
    result = tx.run(
        f"""MATCH p=(a)-[r:FLOWS_TO*]->(b{{lineno:{lineno}, fileid:{fileid}}}) where exists(a.lineno) and exists(a.fileid) RETURN collect(distinct([a.id, a.lineno, a.fileid])) as result"""
    ).single().get('result')
    return result

def get_ancestor_nodes_individually(tx, fileid, lineno, i):
    result = tx.run(
        f"""MATCH p=(a)-[r:FLOWS_TO*{i}..{i}]->(b{{lineno:{lineno}, fileid:{fileid}}}) where exists(a.lineno) and exists(a.fileid) RETURN collect(distinct([a.id, a.lineno, a.fileid])) as result"""
    ).single().get('result')
    return result

def get_descendant_nodes(tx, fileid, lineno):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{lineno}, fileid:{fileid}}})-[r:FLOWS_TO*]->(b) where exists(b.lineno) and exists(b.fileid) RETURN collect(distinct([b.id, b.lineno, b.fileid]))as result"""
    ).single().get('result')
    return result

def get_descendant_nodes_individually(tx, fileid, lineno, i):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{lineno}, fileid:{fileid}}})-[r:FLOWS_TO*{i}..{i}]->(b) where exists(b.lineno) and exists(b.fileid) RETURN collect(distinct([b.id, b.lineno, b.fileid])) as result"""
    ).single().get('result')
    return result

def get_all_sources(tx):
    result = tx.run(
        f"""MATCH (n) WHERE n.is_source = True return collect([n.lineno, n.fileid]) as result"""
    ).single().get('result')
    return result

def get_all_sources_exp(tx):
    result = tx.run(
        f"""MATCH (n) WHERE n.is_source = True return collect([n.lineno, n.funcid]) as result"""
    ).single().get('result')
    return result

def get_all_sinks(tx):
    result = tx.run(
        f"""MATCH (n) WHERE n.type = "AST_ECHO" return collect([n.lineno, n.fileid]) as result"""
    ).single().get('result')
    return result

def get_all_sinks_exp(tx):
    result = tx.run(
        f"""MATCH (n) WHERE n.type = "AST_ECHO" return collect([n.lineno, n.funcid]) as result"""
    ).single().get('result')
    return result

def check_reaches(tx, lineno, fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {lineno}, fileid: {fileid}, is_source:True}})-[r:REACHES*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}}}) RETURN length(p) as result limit 1"""
    ).single().get('result')
    return result

def get_check_reaches(tx, lineno, fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {lineno}, fileid: {fileid}, is_source:True}})-[r:REACHES*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}}}) RETURN collect(p) as result"""
    ).single().get('result')
    return result

def check_reaches2(tx, lineno, fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {lineno}, fileid: {fileid}}})-[r:REACHES*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}, type:"AST_ECHO"}}) RETURN length(p) as result limit 1"""
    ).single().get('result')
    return result

def get_check_reaches2(tx, lineno, fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {lineno}, fileid: {fileid}}})-[r:REACHES*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}, type:"AST_ECHO"}}) RETURN collect(p) as result"""
    ).single().get('result')
    return result

def fileid_to_filename(tx):
    result = tx.run(
        """MATCH (n) WHERE EXISTS(n.full_name) RETURN collect(distinct([n.fileid, n.full_name])) as result"""
    ).single().get('result')
    return result

def check_paths_in_file(tx, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{fileid: {source_fileid}, is_source:True}})-[r:FLOWS_TO*]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}}}) RETURN length(p) as result limit 1""",
        timeout=120
    ).single().get('result')
    return result

def check_paths_in_file_sink(tx, sink_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{dest_lineno}, fileid:{dest_fileid}}})-[r:FLOWS_TO*]->(b{{fileid: {sink_fileid}, type:"AST_ECHO"}}) RETURN length(p) as result limit 1""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_count_source(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {source_lineno}, fileid: {source_fileid}, is_source:True}})-[r:REACHES*0..100]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}}}) RETURN count(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_count_sink(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {source_lineno}, fileid: {source_fileid}}})-[r:REACHES*0..100]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}, type:"AST_ECHO"}}) RETURN count(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_source(tx, sim_node_lineno, sim_node_fieid, sink_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{sim_node_lineno}, fileid:{sim_node_fieid}}})-[r:REACHES*0..100]->(b{{type:"AST_ECHO", fileid:{sink_fileid}}}) RETURN p LIMIT 1 as result"""
    ).single().get('result')
    return result

def get_paths_count_source_file(tx, source_fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{is_source:True, fileid:{source_fileid}}})-[r:FLOWS_TO*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}}}) RETURN count(p) as result"""
    ).single().get('result')
    return result

def get_paths_count_sink_file(tx, sink_fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{node_lineno}, fileid:{node_fileid}}})-[r:FLOWS_TO*]->(b{{type:"AST_ECHO", fileid:{sink_fileid}}}) RETURN count(p) as result"""
    ).single().get('result')
    return result

def get_paths_count_source_file_specific(tx, source_lineno, source_fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{is_source:True, lineno:{source_lineno}, fileid:{source_fileid}}})-[r:FLOWS_TO*]->(b{{lineno:{node_lineno}, fileid:{node_fileid}}}) RETURN count(p) as result"""
    ).single().get('result')
    return result

def get_paths_count_sink_file_specific(tx, sink_lineno, sink_fileid, node_lineno, node_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{node_lineno}, fileid:{node_fileid}}})-[r:FLOWS_TO*]->(b{{type:"AST_ECHO", lineno:{sink_lineno}, fileid:{sink_fileid}}}) RETURN count(p) as result"""
    ).single().get('result')
    return result

def get_paths_count_from_source_to_node(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {source_lineno}, fileid: {source_fileid}, is_source:True}})-[r:REACHES*0..100]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}}}) RETURN length(p) as result limit 1""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_count_from_node_to_sink(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{dest_lineno}, fileid:{dest_fileid}}})-[r:REACHES*0..100]->(b{{lineno: {source_lineno}, fileid: {source_fileid}, type:"AST_ECHO"}}) RETURN length(p) as result limit 1""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_from_source_to_node(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {source_lineno}, fileid: {source_fileid}, is_source:True}})-[r:FLOWS_TO*]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}}}) RETURN collect(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_from_node_to_sink(tx, source_lineno, source_fileid, dest_lineno, dest_fileid):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{dest_lineno}, fileid:{dest_fileid}}})-[r:FLOWS_TO*]->(b{{lineno: {source_lineno}, fileid: {source_fileid}, type:"AST_ECHO"}}) RETURN collect(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def at_least_one_path(tx, node_fileid):
    result = tx.run(
        f"""MATCH p = (a)-[r:FLOWS_TO*1]->(b{{fileid:{node_fileid}}}) WHERE b.fileid <> a.fileid RETURN COLLECT(b.lineno) as result"""
    ).single().get('result')
    return result

def get_paths_from_source_to_node_individually(tx, source_lineno, source_fileid, dest_lineno, dest_fileid, i):
    result = tx.run(
        f"""MATCH p=(a{{lineno: {source_lineno}, fileid: {source_fileid}, is_source:True}})-[r:FLOWS_TO*{i}..{i}]->(b{{lineno:{dest_lineno}, fileid:{dest_fileid}}}) RETURN collect(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_paths_from_node_to_sink_individually(tx, source_lineno, source_fileid, dest_lineno, dest_fileid, i):
    result = tx.run(
        f"""MATCH p=(a{{lineno:{dest_lineno}, fileid:{dest_fileid} }})-[r:FLOWS_TO*{i}..{i}]->(b{{lineno: {source_lineno}, fileid: {source_fileid}, type:"AST_ECHO"}}) RETURN collect(p) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_ith_ith_children(tx, node, childnum1, childnum2):
    logging.debug("get_ith_ith_children")
    # manageFunctionCall manageGenericConstant
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[]->(CHILD)-[]->(RN) WHERE CP.id={nodeid} AND CHILD.childnum={childnum1} AND RN.childnum={childnum2} return RN as result".format(
        nodeid=nodeid, childnum1=childnum1, childnum2=childnum2)).single()
    return convert_cnode_to_gnode(result.get('result')) if result else None

def get_astvar_ith_children(tx, node, childnum):
    logging.debug("get_astvar_ith_children")
    # manageArray
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[]->(CHILD)-[]->(RN) WHERE CP.id={nodeid} AND CHILD.childnum={childnum} AND CHILD.type in ['AST_VAR'] AND RN.childnum=0 return RN as result".format(
        nodeid=nodeid, childnum=childnum)).single()
    return convert_cnode_to_gnode(result.get('result')) if result else None

def ithChildren(tx, node, childnum):
    logging.debug("ithChildren")
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[:PARENT_OF]->(CHILD) WHERE CP.id={nodeid} AND CHILD.childnum={childnum} return CHILD as result".format(
        nodeid=nodeid, childnum=childnum))
    result = result.single()
    return convert_cnode_to_gnode(result.get('result')) if result else None

def ithChildren_new(tx, nodeid, childnum):
    logging.debug("ithChildren")
    #nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[:PARENT_OF]->(CHILD) WHERE CP.id={nodeid} AND CHILD.childnum={childnum} return CHILD as result".format(
        nodeid=nodeid, childnum=childnum)).single()
    return convert_cnode_to_gnode(result.get('result')) if result else None

def get_all_calls_identifiers(tx):
    logging.debug("get_all_calls_identifiers")
    # nodeid = node.properties['id']
    result = tx.run('MATCH p=(A)-[:PARENT_OF]->(B)-[:PARENT_OF]->(C) WHERE A.type = "AST_CALL" and B.type="AST_NAME" and C.type="string" RETURN collect(C.code) AS result').single()
    #'MATCH p = (A) - [:PARENT_OF]->(B), p1 = (A) - [:PARENT_OF]->(D) - [: PARENT_OF]->(E) WHERE A.type = "AST_METHOD_CALL" and B.childnum = 1 and D.childnum = 0 return E.code, B.code'
    result = result.get("result")
    return result if result else []

def get_all_methods_identifiers(tx):
    logging.debug("get_all_calls_identifiers")
    # nodeid = node.properties['id']
    result = tx.run('MATCH p = (A) - [:PARENT_OF]->(B), p1 = (A) - [:PARENT_OF]->(D) - [: PARENT_OF]->(E) WHERE A.type = "AST_METHOD_CALL" and B.childnum = 1 and D.childnum = 0 return collect([E.code, B.code]) as result').single()
    return result if result else []

def get_method_identifier(tx, node):
    logging.debug("get_all_calls_identifiers")
    nodeid = node.properties['id']
    result = tx.run(f'MATCH p = (A) - [:PARENT_OF]->(B), p1 = (A) - [:PARENT_OF]->(D) - [: PARENT_OF]->(E) WHERE A.id = {nodeid} and B.childnum = 1 and D.childnum = 0 return [E.code, B.code] as result').single()
    return result if result else []


def get_all_variable_identifiers(tx):
    logging.debug("get_all_variable_identifiers")
    # nodeid = node.properties['id']
    result = tx.run('MATCH p=(A)-[:PARENT_OF]->(B) WHERE A.type = "AST_VAR" RETURN collect(B.code) as result').single()
    return result if result else []

def get_method_name(tx, node):
    logging.debug("get_method_name")
    nodeid = node.properties["id"]
    result = tx.run(f'MATCH p = (A) - [:PARENT_OF]->(B), p1 = (A) - [:PARENT_OF]->(D) - [: PARENT_OF]->(E) WHERE A.type = "AST_METHOD_CALL" and A.id={nodeid} and B.childnum = 1 and D.childnum = 0 return E.code as object, B.code as method_name').single()
    return result if result else []

def varToName(tx, node):
    logging.debug("varToName")
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[:PARENT_OF]->(CHILD) WHERE CP.id={nodeid} AND CP.type in ['AST_VAR'] AND CHILD.childnum=0 return CHILD as result".format(
        nodeid=nodeid)).single()
    return convert_cnode_to_gnode(result.get('result')) if result else None

def get_children(tx, node):
    logging.debug("get_children")
    # manageEncapsulatedList
    nodeid = node.properties['id']
    result = tx.run("MATCH (CP)-[]->(CHILD) WHERE CP.id={nodeid} with CHILD order by CHILD.id return collect(CHILD) as result".format(
        nodeid=nodeid)).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_alternate_subtree_root(tx, node):
    logging.debug("get_subtree")
    # manageEncapsulatedList
    nodeid = node.properties['id']
    query = f"MATCH (CP)-[r:PARENT_OF*]->(CHILD) WHERE CP.id={nodeid} return [CP.lineno, CP.fileid] as result"
    result = tx.run(query).single().get('result')
    return result

def get_alternate_subtree_child(tx, node):
    logging.debug("get_subtree")
    nodeid = node.properties['id']
    lineno = node.properties['lineno']
    fileid = node.properties['fileid']
    query = f"MATCH (CP{{lineno:{lineno}, fileid:{fileid}}})-[r:PARENT_OF*]->(CHILD{{lineno:{lineno}, fileid:{fileid}}}) return collect(CHILD) as result"
    result = tx.run(query).single().get('result')
    return result

def get_short_subtree(tx, lineno, fileid):
    result = tx.run(
        f"""match (n) where n.fileid = {fileid} and n.lineno = {lineno} return collect(n) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_short_child(tx, root):
    root_id = root['id']
    root_lineno = root['lineno']
    root_fileid = root['fileid']
    result = tx.run(
        f"""MATCH (p{{id:{root_id}, fileid:{root_fileid}, lineno:{root_lineno}}})-[r:PARENT_OF*]->(c{{fileid:{root_fileid}, lineno:{root_lineno}}}) return collect(c) as result""",
        timeout=120
    ).single().get('result')
    return result

def get_other_location(tx, root):
    lineno = root['lineno']
    fileid = root['fileid']
    result = tx.run(
        f"""MATCH (n) WHERE n.fileid <> {fileid} and n.lineno <> {lineno} return collect(distinct([n.lineno, n.fileid])) as result""",
        timeout=120
    ).single().get('result')
    return result

def check_parent(tx, node):
    lineno = node['lineno']
    fileid = node['fileid']
    id = node['id']
    result = tx.run(
        f"""MATCH (p)-[r:PARENT_OF*1]->(c{{id:{id}}}) return p as result""",
        timeout=120
    ).single().get('result')
    return result

def get_subtree(tx, node):
    logging.debug("get_subtree")
    # manageEncapsulatedList
    nodeid = node.properties['id']
    lineno = node.properties['lineno']
    fileid = node.properties['fileid']
    query = f"""match (n) where n.fileid = {fileid} and n.lineno = {lineno} return collect(n) as result"""
    # query = f"MATCH (CP{{lineno: {lineno}, fileid: {fileid}}})-[r:PARENT_OF*]->(CHILD{{lineno:{lineno}, fileid{fileid}}}) return collect(CHILD) as result"
    result = tx.run(query).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_other_subtree_root(tx, node):
    logging.debug("get_subtree")
    # manageEncapsulatedList
    nodeid = node.properties['id']
    lineno = node.properties['lineno']
    fileid = node.properties['fileid']
    query = f"MATCH (CP) WHERE CP.id<>{nodeid} and CP.lineno <>{lineno} return collect(distinct([CP.lineno, CP.fileid])) as result"
    result = tx.run(query).single().get('result')
    return result

def get_other_subtree_child(tx, node):
    logging.debug("get_subtree")
    # manageEncapsulatedList
    # nodeid = node.properties['id']
    lineno = node[0]
    fileid = node[1] #k value is
    query = f"MATCH (CP{{lineno:{lineno}, fileid:{fileid}}})-[r:PARENT_OF*]->(CHILD{{lineno:{lineno}, fileid:{fileid}}}) return collect(CHILD) as result"
    result = tx.run(query).single().get('result')
    return result

def get_children_of_type(tx, node, list_of_types):
    logging.debug("get_children_of_type")
    # manageEncapsulatedList
    nodeid = node.properties['id']
    query = f"MATCH (CP)-[r:PARENT_OF]->(CHILD) WHERE CP.id={nodeid} and CHILD.type in {list_of_types} with CHILD order by CHILD.id return collect(CHILD) as result"
    result = tx.run(query).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def test_getEnclosingTrueCond(driver, nodeid):
    with driver.session() as session:
        print(nodeid)
        gnode = session.write_transaction(get_node_from_id, nodeid)
        return session.write_transaction(getEnclosingTrueCond, gnode)

def test_getConditionsFromFalseBranch(driver, nodeid):
    with driver.session() as session:
        print(nodeid)
        gnode = session.write_transaction(get_node_from_id, nodeid)
        return session.write_transaction(getConditionsFromFalseBranch, gnode)

def test_callToArguments(driver, nodeid):
    with driver.session() as session:
        print(nodeid)
        gnode = session.write_transaction(get_node_from_id, nodeid)
        return session.write_transaction(callToArguments, gnode)

def test_ithChildren(driver, nodeid):
    with driver.session() as session:
        print(nodeid)
        gnode = session.write_transaction(get_node_from_id, nodeid)
        return session.write_transaction(ithChildren, gnode, 0)

### For user interation



def get_sink_node_abs(tx, filename, lineno, timed=False):
    result = tx.run("""
        match (f:Filesystem)
        where f.full_name='{filename}'
        match (a)
        where a.fileid=f.fileid and a.lineno={lineno} and exists((a)-[:FLOWS_TO]-(:AST))
        return a as result
    """.format(lineno=lineno, filename=filename)).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result != None else [None]

def get_back_edge_nodes(tx, node, timed=False):
    logging.debug("get_back_edge_nodes")
    nodeid = node.properties['id']
    query = f"match (a)<-[FLOWS_TO]-(b) where a.id = {nodeid} and a.lineno <= b.lineno return collect(b) as result"
    result = tx.run(query).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_target_node(tx, node, timed=False):
    logging.debug("get_target_node")
    nodeid = node.properties['id']
    query = f"match (a)-[r:FLOWS_TO]->(b) where a.id = {nodeid} and r.flowLabel = false return collect(b) as result"
    result = tx.run(query).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_next_cfg_node(tx, node, timed=False):
    nodeid = node.properties["id"]
    query = f"match (a)-[r:FLOWS_TO]->(b) where a.id = {nodeid} return collect(b) as result"
    result = tx.run(query).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result else []

def get_sink_node_abs_exists_reaches(tx, filename, lineno, timed=False):
    result = tx.run("""
        match (f:Filesystem)
        where f.full_name='{filename}'
        match (a)
        where a.fileid=f.fileid and a.lineno={lineno} and exists((a)-[:FLOWS_TO]-(:AST)) and exists((a)-[:REACHES]-(:AST))
        return a as result
    """.format(lineno=lineno, filename=filename)).single()
    return [result.get('result'), 0] if result != None else [None, 0]

def get_func_call_name(tx, node_id, timed=False):
    result = tx.run("""
        match (a)-[:CALLS]->(b:AST)
        where a.id={nodeid} and b.type='AST_FUNC_DECL'
        match (a)-[:PARENT_OF]->(c)
        where c.type='AST_ARG_LIST'
        return [b.name, c.childnum] as result
    """.format(nodeid=node_id)).single()
    return [result.get('result'), 0] if result != None else [None, 0]

def get_all_func_calls(tx, funcname, timed=False):
    result = tx.run("""
        match (a)-[:CALLS]->(b)
        where a.type='AST_CALL' and b.type='AST_FUNC_DECL' and b.name='{funcname}'
        match (a)-[:PARENT_OF]->(c)
        where c.type='AST_ARG_LIST'
        return collect({{callid: a.id, fileid:a.fileid, nargs:c.childnum, args:c.id}}) as result
    """.format(funcname=funcname)).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result != None else []

def get_identifiers(tx, node, timed=False):
    if node.properties["type"] == "AST_ECHO":
        return ["echo"]
    nodeid = node.properties["id"]
    result = tx.run("""MATCH p=(a)-[r:PARENT_OF*1..]->(b) 
                        where a.id = {nodeid} and b.type = 'string' 
                        return collect(b.code) as result
    """.format(nodeid=nodeid)).single()
    return result.get('result') if result != None else []

def get_function_and_method_defs(tx, timed=False):
    result = tx.run("""MATCH (a:AST) where a.type in ['AST_METHOD', 'AST_FUNC_DECL', 'AST_FUNCTION'] return collect(a) as result
        """).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result != None else []

def get_calls_in_subtree(tx, node):
    nodeid = node.properties["id"]
    result = tx.run("""MATCH p=(a)-[r:PARENT_OF*1..]->(b) 
                            where a.id = {nodeid} and b.type in ['AST_CALL', 'AST_METHOD_CALL']
                            return collect(b) as result
        """.format(nodeid=nodeid)).single()
    return [convert_cnode_to_gnode(node) for node in result.get('result')] if result != None else []

def test(tx, timed=False):
    query = "MATCH p=(b)-[r:PARENT_OF]->(a) where a.type='AST_NAME' RETURN collect(b.type) as result"
    result = tx.run(query).single()
    return [result.get('result'), 0] if result != None else [None, 0]

def test1(tx, timed=False):
    query = "MATCH p=(b)-[r:PARENT_OF]->(a) where a.type='string' RETURN collect(b.type) as result"
    result = tx.run(query).single()
    return [result.get('result'), 0] if result != None else [None, 0]

###




if __name__ == '__main__':

    from neo4j import GraphDatabase

    uri = 'bolt://localhost:7687'
    user = 'neo4j'
    password = 'user'
    INVALID_NODEID = 83740932

    print("Connecting...")
    driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)

    with driver.session() as session:
        paths = session.write_transaction(get_flows_to_path_adv, 354969, 354397, flag=1)
        print(paths)
        print(len(paths))
        # for path in paths:
        #     if 352741 in path and 352765 in path:
        #         print(path)
        #         break


    exit(0)
    print(test_ithChildren(driver, 8979))
    exit(0)
    print(test_callToArguments(driver, 19490))

    print(test_getConditionsFromFalseBranch(driver, 19490))
    print(test_getConditionsFromFalseBranch(driver, 19436))
    print(test_getConditionsFromFalseBranch(driver, 19429))

    print(test_getEnclosingTrueCond(driver, 19490))
    print(test_getEnclosingTrueCond(driver, 19439))
    print(test_getEnclosingTrueCond(driver, 19428))
    print(test_getEnclosingTrueCond(driver, 19509))
    print(test_getEnclosingTrueCond(driver, 19466))
    print(test_getEnclosingTrueCond(driver, 19446))

