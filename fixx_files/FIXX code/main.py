import json
import os.path
import sys
import argparse
import time
import globals
from docker_utilities import *
from migration_neo4j_4.neo4j_driver import Neo4jDriver, init
import requests

parser = argparse.ArgumentParser()
parser.add_argument("--buildcpg", help='build cpg from the code', action='store_true')
parser.add_argument("--loadcpg", help='load cpg from previously saved cpg', action='store_true')
parser.add_argument("-n", help='application name in /var/www/html')
parser.add_argument("--neo4jhttpport", help='Neo4j HTTP connection port. Use value between 7474-7574. If this argument is missing, default port is 7474')
parser.add_argument("--neo4jboltport", help='Neo4j BOLT connection port. Use value between 7687-7787. If this argument is missing, default port is 7687.')
parser.add_argument("--nodocker", help='run outside docker (for dev only)', action='store_true')
parser.add_argument("--similarity", help='run similarity analysis', action='store_true')

def main(argv):
    args = parser.parse_args()
    print("these are the arguments", args)
    globals.application_name = args.n
    enriched = True
    #start_services()
    if args.neo4jhttpport:
        globals.NEO4J_HTTP_PORT = args.neo4jhttpport
    if args.neo4jboltport:
        globals.NEO4J_BOLT_PORT = args.neo4jboltport
    if args.nodocker:
        globals.PROJECT_PATH = os.getcwd()
        top_dir = os.path.split(globals.PROJECT_PATH)[0]
        globals.RESULTS_DIR = os.path.join(top_dir, "results")
    else:
        start_services()

    from application_manager import ApplicationManager
    driver = Neo4jDriver()
    from similarity_analyzer import SimilarityAnalyzer
    if args.buildcpg:
        app_manager = ApplicationManager(driver=driver)
        app_manager.create_csvs(globals.application_name)
        app_manager.clean_csvs(globals.application_name)
        app_manager.load_csvs(globals.application_name)
        app_manager.activate_neo4j_database(globals.application_name)
        app_manager.do_additional_analysis(enriched)  #run db_scripts on the Neo4J database
        app_manager.dump_neo4j_database(globals.application_name)
    if args.loadcpg:
        if args.buildcpg:
            print('--buildcpg and --loadcpg are mutually exclusive. They operate on the same Neo4j database and may leave it in an inconsistent state.')
        else:
            app_manager = ApplicationManager(driver=driver)
            app_manager.load_database(globals.application_name)
    if args.similarity:
        similarity_analyzer = SimilarityAnalyzer()
        similarity_analyzer.run_analysis()


    # dynamic_analyzer.application_manager.setup_mysql_database('oscommerce')

def init(app_name):
    init()
    app_manager = ApplicationManager()
    app_manager.load_database(globals.application_name)

if __name__ == '__main__':
    #start_services()
    #start_neo4j()
    main(sys.argv)
    #time.sleep(9999)