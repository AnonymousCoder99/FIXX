import os
from docker_utilities import *
# this file is responsible for creating the code property graph, invoking extended dataflow analysis,
# and managing the neo4j databases
import sys
from db_scripts import *
from migration_neo4j_4.neo4j_driver import *
import shutil
import globals

class ApplicationManager:
    def __init__(self, driver=None):
        self.html_folder = '/var/www/html/'
        self.neo4j_db_folder = '/var/lib/neo4j/data/databases/'
        self.php_joern_path = os.getenv('PHP_JOERN_PATH')
        self.joern_path = os.getenv('JOERN_PATH')
        self.project_path = globals.PROJECT_PATH
        self.intermediate_results_path = '/opt/project/intermediate_results'
        if not os.path.isdir(self.intermediate_results_path):
            os.mkdir(self.intermediate_results_path, 0o777)
        self.schemas = '/opt/project/neo4j_schemas'
        self.dump_files_directory = '/opt/project/dumpfiles/'
        self.mysql_schemas_path = '/opt/project/mysql_schemas'
        self.driver = driver
        #setup_neo4j_driver()



    def create_csvs(self, application_name):
        application_path = os.path.join(self.html_folder, application_name)
        results_path = os.path.join(self.intermediate_results_path, application_name)
        if not os.path.isdir(results_path):
            os.system('mkdir ' + results_path)


        os.chdir(results_path)
        path = os.getcwd();
        print("Current path: " + path)
        # fix shell script coming from Windows environments, remove \r from new lines
        command1 = os.path.join(globals.PROJECT_PATH, "convert_newlines.sh") + " " + os.path.join(self.php_joern_path,
                                                                                                  "php2ast")
        print("Command: " + command1)
        os.system(command1)
        command1 = os.path.join(globals.PROJECT_PATH, "convert_newlines.sh") + " " + os.path.join(self.joern_path,
                                                                                                  "phpast2cpg")
        print("Command: " + command1)
        os.system(command1)
        #create AST
        print(application_path, self.php_joern_path)
        command = os.path.join(self.php_joern_path, "php2ast") + " -f jexp -n nodes.csv -r edges.csv " + application_path
        print("Command: " + command)
        os.system(command)

        #create CPG
        os.chdir(results_path)
        path = os.getcwd()
        print("Current path: " + path)
        command = os.path.join(self.joern_path, "phpast2cpg") + " nodes.csv edges.csv"
        print("Command: " + command)
        return os.system(command)

    def clean_csvs(self, application_name):
        results_path = os.path.join(self.intermediate_results_path, application_name)
        if not os.path.isdir(results_path):
            os.mkdir(results_path)

        os.chdir(self.project_path)
        working_path = os.getcwd();
        sleep(2)
        print("Current Path: " + working_path)
        command = './clean_csvs.sh ' + '-r ' + results_path + ' ' + application_name # + ' | tee logs/b'
        print("Command: " + command)
        os.system(command)
    
    def delete_neo4j_database_file(self, application_name):
        if os.path.exists(f'/var/lib/neo4j/data/databases/{application_name}'):
            print("WARNING database already exists...")
            print("Deleting the existing database file")
            shutil.rmtree(f'/var/lib/neo4j/data/databases/{application_name}')
            if os.path.exists(f'/var/lib/neo4j/data/transactions/{application_name}'):
                shutil.rmtree(f'/var/lib/neo4j/data/transactions/{application_name}')

    def load_csvs(self, application_name):
        # check if database exists already
        # if it does, then delete it
        self.delete_neo4j_database_file(application_name)
        print('Loading CSVS===========================================================================================')
        sleep(2)
        results_path = os.path.join(self.intermediate_results_path, application_name)
        neo4j_admin_path = '/usr/local/lib/neo4j/bin/neo4j-admin'
        options = ' --nodes=\'' + self.schemas + '/nodes_header.csv,nodes.csv\'' \
                + ' --relationships=\'' + self.schemas + '/cpg_edges_header.csv,cpg_edges.csv\'' \
                + ' --relationships=\'' + self.schemas + '/edges_header.csv,edges.csv\'' \
                + ' --id-type=INTEGER --ignore-empty-strings=true' \
                + ' --ignore-extra-columns=true --multiline-fields=true' \
                + ' --delimiter=\'\t\'' \
                + ' --database=' + application_name
        command = neo4j_admin_path + ' import ' + options
        os.chdir(results_path)
        path = os.getcwd()
        print("Current path: " + path)
        print("Command: " + command)
        os.system(command)

    def activate_neo4j_database(self, database_name):
        stop_neo4j()
        database_path = '/var/lib/neo4j/data/databases/' + database_name
        #seems like the only way to use another database is to put its name into the conf file
        #stop_neo4j()
        command = 'sed -i s/dbms.default_database=.*/dbms.default_database=' + database_name +'/g /etc/neo4j/neo4j.conf'
        os.system(command)
        start_neo4j()

    def activate_neo4j_database_no_restart(self, database_name):
        database_path = '/var/lib/neo4j/data/databases/' + database_name
        # seems like the only way to use another database is to put its name into the conf file
        # stop_neo4j()
        command = 'sed -i s/dbms.default_database=.*/dbms.default_database=' + database_name + '/g /etc/neo4j/neo4j.conf'
        os.system(command)

    def is_loaded_neo4j_database(self, database_name):
        str_to_search = "dbms.default_database="+database_name
        db_path = os.path.join("/var/lib/neo4j/data/databases/", database_name)
        with open('/etc/neo4j/neo4j.conf') as f:
            if(str_to_search in f.read()):
                if(os.path.isdir(db_path)):
                    return True
                else:
                    return False
            else:
                return False

    def load_neo4j_database(self, dump_file_path, database_name):
        command = '/usr/bin/neo4j-admin load --database=' + database_name + ' --from=' + dump_file_path
        os.system(command)

    def load_database(self, app_name, enriched=True):
        stop_neo4j()
        #always reload from scratch. If directory exists it will not reload
        dir_db = os.path.join("/var/lib/neo4j/data/databases", app_name)
        dir_transactions = os.path.join("/var/lib/neo4j/data/transactions", app_name)
        if os.path.isdir(dir_db):
            shutil.rmtree(dir_db)
        if os.path.isdir(dir_transactions):
            shutil.rmtree(dir_transactions)
        if enriched:
            dump_file_path = os.path.join(os.path.join(self.dump_files_directory, app_name), app_name + '_enriched.dump')
        else:
            dump_file_path = os.path.join(os.path.join(self.dump_files_directory, app_name),
                                          app_name + '_original.dump')
        self.load_neo4j_database(dump_file_path, app_name)
        self.activate_neo4j_database_no_restart(app_name)
        start_neo4j()

        #return self.load_neo4j_database(self.dump_files_directory)

    def dump_neo4j_database(self, app_name, enriched=True):
        stop_neo4j()
        dump_file_dir = os.path.join(self.dump_files_directory, app_name)
        if not os.path.isdir(dump_file_dir):
            os.makedirs(dump_file_dir, 0o777, exist_ok=True)
        if enriched:
            dump_file_path = os.path.join(dump_file_dir, app_name) + '_enriched.dump'
        else:
            dump_file_path = os.path.join(dump_file_dir, app_name) + '_original.dump'
        if os.path.exists(dump_file_path):
            os.remove(dump_file_path)
        command = '/usr/bin/neo4j-admin dump --database=' + app_name + ' --to=' + dump_file_path
        os.system(command)
        start_neo4j()

    def do_additional_analysis(self, enriched=True):
        uri = 'bolt://localhost:7687'
        user = 'neo4j'
        password = 'user'
        # driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
        if self.driver:
            driver = self.driver.d
        else:
            driver = get_neo4j_driver()
        print('Adding more edges to graph...This might take a while! ')
        first_required_scripts(driver)
        # exit()
        # add_correct_edges_v2(driver)
        # exit()
        print("Adding all other DDG's accross files(only required for backtrack analysis; exit if not required)")
        print("Adding is_source property to nodes")
        add_is_source_property(driver)
        if enriched == False:
            return
        print(datetime.now())
        print("Adding REACHES edges between argument and parameters -> function definition and function calls...")
        add_reaches_to_func_def_call(driver)
        print(datetime.now())
        #print("Adding REACHES edges between class properties...")
        #add_class_property_ddg(driver)
        print("Adding REACHES edges in function return statements...")
        add_function_return_ddg(driver)
        print("Adding FLOWS_TO edges between function call and function definition")
        add_function_call_cfg(driver)
        print("Adding REACHES edges between INSERT and SELECT sql queries performed on the same table")
        add_reaches_db_query(driver)
        #driver.close()


    #try to automate the application installation as much as possible
    # for those apps that come with .sql files that need to be loaded externally. 'docker commit' is another option
    def setup_application(self, app_name):
        schema_path = self.mysql_schemas_path + '/' + app_name
        if app_name == 'schoolmate':
            # because mysqldump requires an empty database
            command = 'mysql -u root -e \"create database schoolmate\"';
            os.system(command)
            # because connecting as root sometimes fails
            command = 'mysql -u root schoolmate < ' + self.mysql_schemas_path + '/create_default_user.sql'
            os.system(command)
            # import the actual tables and data. change file index.php to reflect this username, password, and db_name
            command = 'mysql -u root schoolmate < ' + schema_path + '/schoolmate.sql'
            os.system(command)
        elif app_name == 'oscommerce':
            command = 'mysql -u root -e \"create database oscommerce\"';
            os.system(command)
            command = 'mysql -u root oscommerce < ' + self.mysql_schemas_path + '/create_default_user.sql'
            os.system(command)
        elif app_name == 'hotcrp260': #after installation, point browser to: localhost/hotcrp260. User form to create new user. The first user that is created is automatically given admin privileges.
            command = 'printf "\n\n\n\n" | /var/www/html/hotcrp260/Code/createdb.sh --user=root --password=user'
            os.system(command)
        elif app_name == "cephoenix1050": #finish installation on the browser: localhost/cephoenix1050/install
            command = 'mysql -uroot -puser -e \"create database cephoenix\"'
            os.system(command)
        elif app_name == "HospitalManagementSystemProject": #php gurukul hospital management
            command = 'mysql -uroot -puser -e \"create database hms\"'
            os.system(command)
            command = 'mysql -uroot -puser hms < /var/www/html/hmsp/SQL_File/hms.sql'
            os.system(command)
        elif app_name == 'collabtive': #finish installation: point browser to localhost/collabtive/install.php
            command = 'chmod 777 -R /var/www/html/collabtive/files/'
            os.system(command)
            command = 'chmod 777 -R /var/www/html/collabtive/config/standard/config.php'
            os.system(command)
            command = 'chmod 777 -R /var/www/html/collabtive/templates_c'
            os.system(command)
            command = 'apt install php7.2-xml'
            os.system(command)
            command = 'apt install php7.2 - mbstring'
            os.system(command)
            command = 'mysql -uroot -puser -e \"create database collabtive\"'
            os.system(command)
            command = 'php /var/www/html/collabtive/composer.phar install' #this may need to be done inside the container from the local folder
            os.system(command)


def test(argv):
    application_manager = ApplicationManager()
    #start_neo4j()

    application_manager.dump_files_directory = application_manager.dump_files_directory+'/test-apps'

    for app_name in os.listdir(application_manager.html_folder):
        stop_neo4j()
    #    application_manager.load_neo4j_database(os.path.join(application_manager.dump_files_directory + '/' + app_name, app_name + '-original.dump'), app_name)
    #    application_manager.activate_neo4j_database(app_name)
    #    start_neo4j()

        print('Building CPG for: ' + os.path.join(application_manager.html_folder, app_name))
        application_manager.create_csvs(app_name)
        application_manager.clean_csvs(app_name)
        application_manager.load_csvs(app_name)
        application_manager.activate_neo4j_database(app_name)
        if not os.path.isdir(application_manager.dump_files_directory+'/'+app_name):
            os.mkdir(application_manager.dump_files_directory+'/'+app_name)
        application_manager.dump_neo4j_database(app_name, os.path.join(application_manager.dump_files_directory + '/' + app_name, app_name+'-original.dump'))
        start_neo4j()
        if app_name == 'schoolmate':
            application_manager.doAdditionalAnalysis()
            stop_neo4j()
            application_manager.dump_neo4j_database(app_name, os.path.join(application_manager.dump_files_directory + '/' + app_name, app_name + '-enriched.dump'))


    #stop_neo4j()
    #application_manager.create_csvs('oscommerce')
    #application_manager.clean_csvs('oscommerce')
    #application_manager.load_csvs('oscommerce')
    #stop_neo4j()
    #application_manager.activate_neo4j_database('oscommerce')
    #start_neo4j()
    #start_neo4j()
    #stop_neo4j()

    #dump_file_path = application_manager.dump_files_directory + '/' + 'Analysis result files/collabtive 3.1/collabtive_v2.dump'
    #application_manager.load_neo4j_database(dump_file_path, 'collabtive-3.1')

    #dump_file_path = application_manager.dump_files_directory + '/' + 'Analysis result files/cephoenix 1.0.5.0/cephoenix_v2_28_july.dump'
    #application_manager.load_neo4j_database(dump_file_path, 'cephoenix-1.0.5.0')

    #application_manager.activate_neo4j_database('ce-phoenix')
    #application_manager.doAdditionalAnalysis()
    sleep(5)


# if __name__ == '__main__':
#     #start_services()
#     #start_neo4j()
#     test(sys.argv)