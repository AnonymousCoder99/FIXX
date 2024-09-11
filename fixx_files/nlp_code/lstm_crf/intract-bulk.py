"""Interact with a model"""

__author__ = "Guillaume Genthial"

from pathlib import Path
import functools
import json
import csv
import pandas as pd
import tensorflow as tf
import json
from main import model_fn
import requests
from bs4 import BeautifulSoup
import argparse
from urllib.request import Request, urlopen

#create a file named cve_list.csv and populate it with all the cves before running the python file
with open("C://Users/neilp/Downloads/uic-master (1)/uic-master/navex_docker/FIXX/fixx_files/nlp_code/lstm_crf/cve_list.csv") as fp:
    lines = fp.readlines()

jsonfile = open("C://Users/neilp/Downloads/uic-master (1)/uic-master/navex_docker/FIXX/fixx_files/nlp_code/results/"+"codeastro"+ "/results.csv", "w")
jsonfile.write("Testing\n")

counter = 1
for l in lines:
    print(counter)
    counter += 1
    name = l.split(",", 3)[0]
    LINE = l.split(",", 3)[1]
    #links = l.split(",", 3)[2]

    DATADIR = 'C://Users/neilp/Downloads/uic-master (1)/uic-master/navex_docker/FIXX/fixx_files/nlp_code/data/example'
    PARAMS = 'C://Users/neilp/Downloads/uic-master (1)/uic-master/navex_docker/FIXX/fixx_files/nlp_code/lstm_crf/model_details/params.json'
    MODELDIR = 'C://Users/neilp/Downloads/uic-master (1)/uic-master/navex_docker/FIXX/fixx_files/nlp_code/lstm_crf/model_details/model'


    def pretty_print(line, preds):
        print("\n\n\nline is", line)
        words = line.strip().split()
        lengths = [max(len(w), len(p)) for w, p in zip(words, preds)]

        padded_words = [w + (l - len(w)) * '' for w, l in zip(words, lengths)]
        padded_preds = [p.decode() + (l - len(p)) * '' for p, l in zip(preds, lengths)]

        pred_val_df = pd.DataFrame({
            'pred': padded_preds,
            'word': padded_words

        })
        myDict = dict(zip(padded_words, padded_preds))  ## all we need to export into cve

        table = 'mytable'
        newdict = {}
        vuln = ""
        app = ""
        ver = ""
        fil = ""
        rel = ""
        param = ""
        id = ""
        val = ""
        print("dictionary is", myDict)
        for x, y in myDict.items():
            if y == 'B-vulnerability' or y == 'I-vulnerability':
                vuln += x + " "
            elif y == 'B-application' or y == 'I-application':
                app += x + " "
            elif y == 'B-version' or y == 'I-version':
                ver += x + " "
            elif y == 'B-relevant_term' or y == 'I-relevant_term':
                rel += x + " "
            elif y == 'B-file':
                fil += x + " "
            elif y == 'B-parameter':
                param += x + " "
            elif y == 'B-id':
                id += x + " "
            elif y == 'B-value':
                val += x + " "
        myDict[vuln] = 'N-vulnerability'
        myDict[app] = 'N-application'
        myDict[ver] = 'N-version'
        myDict[rel] = 'N-relevant'
        myDict[fil] = 'N-file'
        myDict[param] = 'N-parameter'
        myDict[id] = 'N-id'
        myDict[val] = 'N-val'

        for k, i in myDict.items():

            if (
                    i == 'N-application' or i == 'N-version' or i == 'N-vulnerability' or i == 'B-file' or i == 'B-function' or i == 'N-relevent' or i == 'B-parameter'):
                newdict[myDict[k]] = k

        columns_string = '(' + ', '.join(newdict.keys()) + ')'
        values_string = '(' + ', '.join(map(str, newdict.values())) + ')'
        sql = """INSERT INTO %s %s
             VALUES %s""" % (table, str(columns_string), str(values_string))
        
        sql2 = """ vuln_variable_list = [];  g.V().filter {it.code == "%s"}  //MAY: vulnerable variables
                   .sideEffect{vuln_variable_name = it.code}
                   .parents()
                   .filter {it.type == "AST_DIM"}
                   .as('variables')
                   .toFileAbs()
                   .filter {it.name.contains("/%s")} // MUST: File name 
                   .sideEffect{fileName = it.name}
                   .back('variables')
                   .sideEffect{vuln_variable_list = it.ithChildren(1).code.toList()}
    
                   //.transform{vuln_variable_list}
                   .statements()
                   .sideEffect{varnames = getUsedVariablesNew(it)}
                   .out()  // special case: there has to be two out becuase AST_IF is of "statements" type 
                   .out()
                   .sideEffect{varnames = getUsedVariablesNew(it)}
                   .as('stmt')
    
                   .outE(DATA_FLOW_EDGE).filter{it.var in varnames}.inV()
                  //.transform{it.var}
                   .astNodes()
    
                  .loop('stmt'){it.object.type != TYPE_CALL  && it.object.type != TYPE_METHOD_CALL && it.object.type != TYPE_STATIC_CALL}
                  .dedup()
                  //.out(CALLS_EDGE)
                  //.dedup()
                  //.path{it.id}{it.lineno}{it.type}
                  // .as('pathToSinks')
                   //.out(DATA_FLOW_EDGE)
                   //.loop('pathToSinks'){it.object. != "mysql_query"}
                   //ithChildren(0).out().code
    
    
                filter{"%s" == (it.name) && it.type== "File"}
                           .as('children')
                           .out()
                           .loop('children'){it.object.code != "category"}
                           .filter{it.in().type == "AST_VAR"}
                //.sideEffect{nodeBeforeVar = it.parents().ithchildren(varNodeChildNum-1).astNodes()
                                  .filter{it.type == "string"}
                                  .or(
                                       _().filter{it.code.contains("'")}
                                       .transform{context = "SINGLE_QUOTES"}
                                        ,
                                       _().filter{it.code.contains('"')}
                                       .transform{context = "DOUBLE_QUOTES"}
                                       ,
                                       _().filter{!it.contains("'") && !it.code.contains("'") }
                                       .transform{context = "NO_QUOTES"}
                                      ) }
    
                """ % (newdict['B-parameter'] if 'B-parameter' in newdict.keys() else "Not Exist",
                       newdict["B-file"] if 'B-file' in newdict.keys() else "Not Exist",
                       newdict["B-file"] if 'B-file' in newdict.keys() else "Not Exist")
        

        import csv
        dic_buffer = ' '
        for key, val in myDict.items():
            if val != 'O':
                dic_buffer += key + " : " + val + ", "

        with open('results/csv-out-xss-2.csv', 'a', newline='') as csvfile:
            fieldnames = ['CVE', 'TOKENS']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writerow({'CVE': name, 'TOKENS': dic_buffer})

        data = {}

        data['CVEID'] = name
        data['CVEURL'] = 'https://cve.mitre.org/cgi-bin/cvename.cgi?name=' + name
        data['APPNAME'] = ''
        data['APPVERSION'] = ''
        data['FILES'] = []
        data['PARAMS'] = []
        data['VULNERABILITY'] = ''
        data['RELEVANT'] = []
        data['IDVAL'] = {}
        for key, val in myDict.items():
            if val != 'O' and 'N-' in val:
                if 'N-application' in val:
                    data['APPNAME'] = key
                elif 'N-version' in val:
                    data['APPVERSION'] = key
                elif 'N-file' in val:
                    data['FILES'] += [key]
                elif 'N-vulnerability' in val:
                    data['VULNERABILITY'] = key
                elif 'N-relevant' in val:
                    data['RELEVANT'] += [key]
                elif 'N-parameter' in val:
                    data['PARAMS'] += [key]


        url = data['CVEURL']
        #reqs = requests.get(url)
        reqs = Request(url)
        html_page = urlopen(reqs)
        soup = BeautifulSoup(html_page, 'lxml')

        urls = []
        ref_links = []
        temp_link = []
        for link in soup.find_all('a'):
            ref_links.append(link.get('href'))

        tbody = soup.find_all('table')
        tds = []
        for link2 in tbody:
            tds = link2.find_all('td')
            
        temp_link.append(tds)

        #print('\n\n\n\ntemp_link2 is', temp_link)

        
        #for x in range(0, len(temp_link)):
            #if temp_link[x].find('Description') > -1:
                #print(temp_link[x])

        data['LINKS'] = ref_links
        #print("\nFirst one is", data['LINKS'][0])

        final_links = []
        for i in range(0, len(data['LINKS'])):
            if ((data['LINKS'][i]).find('https')) > -1 or (data['LINKS'][i].find('http')) > -1:
                final_links.append(data['LINKS'][i])
            if ((data['LINKS'][i]).find('table')) > -1:
                temp_link.append(data['LINKS'][i])

        del final_links[:13]
        del final_links[-9:]
        data['LINKS'] = final_links

        #print("\n\n\n\n\n\n", temp_link)
        print("\nThe Json file for this CVE is stored in the results folder")


        ##results to be stored in json files
        cve_details = {}
        for key, val in data.items():
            if len(val) != 0:
                cve_details[key] = val

        jsonfile.write(str(cve_details))
        jsonfile.write("\n")

        with open(name + '.json', 'w+') as file:
            json.dump(cve_details, file, indent=4)

        print("\nThe extraction process is complete and the results of each of the CVEs are available in a JSON format inside the results folder.")

        return final_links


    def detailed_extractor(detailed_data, text):
        for x in range(0, len(text)):
            if 'parameter' in text[x]:
                detailed_data['PARAMS'] += [text[x-1]]
            if '.php' in text[x] or '/' in text[x]:
                detailed_data['FILES'] += [text[x]]
            if 'file' in text[x]:
                detailed_data['FILES'] += [text[x-1]]
            if '$' in text[x]:
                detailed_data['VARIABLES'] += [text[x]]
        return detailed_data

    def predict_input_fn(line):
        # Words
        words = [w.encode() for w in line.strip().split()]
        nwords = len(words)

        # Wrapping in Tensors
        words = tf.constant([words], dtype=tf.string)
        nwords = tf.constant([nwords], dtype=tf.int32)

        return (words, nwords), None


    if __name__ == '__main__':
        with Path(PARAMS).open() as f:
            params = json.load(f)

        params['words'] = str(Path(DATADIR, 'vocab.words.txt'))
        params['chars'] = str(Path(DATADIR, 'vocab.chars.txt'))
        params['tags'] = str(Path(DATADIR, 'vocab.tags.txt'))
        params['glove'] = str(Path(DATADIR, 'glove.npz'))

        estimator = tf.estimator.Estimator(model_fn, MODELDIR, params=params)
        predict_inpf = functools.partial(predict_input_fn, LINE)
        finale_link=[]
        detailed_data={}
        detailed_data['FILES'] = []
        detailed_data['PARAMS'] = []
        lin_es2 = []
        lin_es = []
        for pred in estimator.predict(predict_inpf):
            finale_link = pretty_print(LINE, pred['tags'])
            break
        # print("\n\nfinr", finale_link)
        # for detailed_link in finale_link:
        #     res1 = requests.get(detailed_link)
        #     soup1 = BeautifulSoup(res1.content, "html.parser")
        # #
        #     print("\nThis is the output for the code-formatted text from the detailed webpages: ", detailed_data, "\n")
        # #
        #     string1 = soup1.find_all('p', {'dir':'auto'})
        #     string2 = soup1.find_all('p')
        #     lin_es += [strig.get_text() for strig in string1]
        #     lin_es2 += [strig2.get_text() for strig2 in string2]
        #
        # print("line_s", lin_es)
        # if len(lin_es) > 0:
        #     for y in range(0, len(lin_es)):
        #         lin_es += lin_es[y].split( ) #now a list
        #         detailed_data = detailed_extractor(detailed_data, lin_es)
        # print("\n\ndetailed", detailed_data)
        # #
        # # string2 = soup1.find_all('p')
        # if len(lin_es2) > 0:
        #     lin_es2 = str(lin_es2)
        #     for pred in estimator.predict(predict_inpf):
        #         link = pretty_print(lin_es2, pred['tags'])
        #         break
        # #
        # print("detailed output", link)
