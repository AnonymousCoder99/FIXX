import csv

from EnhancedAnalysis import VulnerablePath
import operator
import sys
import os
import json
import pickle
from datetime import datetime
import itertools
from migration_neo4j_4.cypher_queries import *
from db_scripts import *
import warnings
# from neo4j import ExperimentalWarning
import argparse
import traceback

search_result = []
def get_cond_if(qi, nodeid):
    return qi.get_conditional_stmt_if(nodeid)

def get_cond_while(qi, nodeid):
    return qi.get_conditional_stmt_while(nodeid)

def get_cond_switch(qi, nodeid):
    return qi.get_conditional_stmt_switch(nodeid)

def get_cond_foreach(qi, nodeid):
    return qi.get_conditional_stmt_foreach(nodeid)

def get_reaches(qi, nodeid):
    return qi.get_reaches_edges(nodeid)

def get_reaches(qi, nodeid):
    return qi.get_reaches_edges(nodeid)

def append_node(output, node, d):
    if node:
        output.append({
            "node": node[0],
            "depth": d
        })

def find_cond_stmt(node, d, qi):
    outputList = []
    if d < 3:
        append_node(outputList, get_cond_if(qi, node.properties["id"]), d + 1)
        append_node(outputList, get_cond_while(qi, node.properties["id"]), d + 1)
        append_node(outputList, get_cond_switch(qi, node.properties["id"]), d + 1)
        append_node(outputList, get_cond_foreach(qi, node.properties["id"]), d + 1)
    return outputList

def addDistinct(results, list2):
    for elem in list2:
        isContained = False
        for prev_result in results:
            if prev_result.get("node").properties["id"] == elem.get("node").properties["id"]:
                isContained = True
                break
        if not isContained:
            results.append(elem)

def find_reaches(node, d, qi):
    outputList = []
    append_node(outputList, get_reaches(qi, node.properties["id"]), d)
    return outputList

def rec_search_reaches(elem, qi):
    if elem.get("depth") >= 3:
        return
    reaches_list = find_reaches(elem.get("node"), elem.get("depth"), qi)

    for reaches_elem in reaches_list:
        rec_search_cond(reaches_elem, qi)
        rec_search_reaches(reaches_elem, qi)

#checked
def rec_search_cond(elem, qi):
    local_result = find_cond_stmt(elem.get("node"), elem.get("depth"), qi)
    if local_result:
        addDistinct(search_result, local_result)

    for elem in local_result:
        rec_search_reaches({"node": elem.get("node"), "depth": elem.get("depth")}, qi)


#checked
def add_to_ddgpath(extracted_node, DDGpath):
    for index, node in enumerate(DDGpath):
        if node.properties["id"] == extracted_node.properties["id"]:
            return
        if node.properties["lineno"] > extracted_node.properties["lineno"]:
            DDGpath.insert(index, extracted_node)
            return