import os
from time import sleep
import globals

def start_services():
    #os.system("service mysql start")
    status = os.system("service apache2 start")
    status = os.system("service mosquitto start")
    status = os.system("/etc/init.d/mariadb start")

    #start neo4j

    command = 'sed -i s/#dbms.connector.http.listen_address=:7474/dbms.connector.http.listen_address=:' + str(globals.NEO4J_HTTP_PORT) + '/g /etc/neo4j/neo4j.conf'
    os.system(command)

    command = 'sed -i s/#dbms.connector.http.advertised_address=:7474/dbms.connector.http.advertised_address=:' + str(globals.NEO4J_HTTP_PORT) + '/g /etc/neo4j/neo4j.conf'
    os.system(command)

    command = 'sed -i s/#dbms.connector.bolt.listen_address=:7687/dbms.connector.bolt.listen_address=:' + str(globals.NEO4J_BOLT_PORT) + '/g /etc/neo4j/neo4j.conf'
    os.system(command)

    command = 'sed -i s/#dbms.connector.bolt.advertised_address=:7687/dbms.connector.bolt.advertised_address=:' + str(globals.NEO4J_BOLT_PORT) + '/g /etc/neo4j/neo4j.conf'
    os.system(command)

    os.system("neo4j start")

    # import warnings
    # warnings.filterwarnings("ignore")
    sleep(20)

def setup_applications():
    #osTicket
    os.system("mysql -u root mysql < ../dependencies/create_default_user.sql")
    os.system("cp /var/www/html/osTicket-1.14.2/include/ost-sampleconfig.php /var/www/html/osTicket-1.14.2/include/ost-config.php")


def start_neo4j():
    os.system("neo4j start")
    sleep(15)

def stop_neo4j():
    os.system("neo4j stop")
    #because neo4j turns into a zombie with 'neo4j stop'
    #and the start/stop script checks for the file below to see if neo4jis running.
    if(os.path.isfile('/var/run/neo4j/neo4j.pid')):
        os.remove('/var/run/neo4j/neo4j.pid')
    sleep(5)

