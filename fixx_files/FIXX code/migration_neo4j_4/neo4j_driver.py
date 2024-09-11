from neo4j import GraphDatabase
import globals

#driver = None

def init():
	uri = 'bolt://127.0.0.1:' + str(globals.NEO4J_BOLT_PORT)
	user = 'neo4j'
	password = 'user'
	global driver
	driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)


def get_neo4j_driver(driver=None):
	if not driver:
		uri = 'bolt://127.0.0.1:' + str(globals.NEO4J_BOLT_PORT)
		user = 'neo4j'
		password = 'user'
		driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
		return driver
	else:
		return driver

class Neo4jDriver:
    def __init__(self, user='neo4j', password='user'):
        self.uri = 'bolt://127.0.0.1:' + str(globals.NEO4J_BOLT_PORT)
        self.user = user
        self.password = password
        self.d = GraphDatabase.driver(self.uri, auth=(self.user, self.password), encrypted=False)

