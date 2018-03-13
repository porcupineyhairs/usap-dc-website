import urllib2
import json
import xml.dom.minidom as minidom
from lib.ezid import formatAnvlRequest, issueRequest, encode, MyHTTPErrorProcessor
#import lxml.etree as ET
import os
import psycopg2
import sys
import requests
from flask import session
from subprocess import Popen, PIPE

UPLOAD_FOLDER = "upload"
DATASET_FOLDER = "dataset"
SUBMITTED_FOLDER = "submitted"
DCXML_FOLDER = "submitted"
ISOXML_FOLDER = "watch/isoxml"
DOCS_FOLDER = "doc"
DOI_REF_FILE = "inc/doi_ref"
CURATORS_LIST = "inc/curators.txt"
EZID_FILE = "inc/ezid.json"
DATACITE_TO_ISO_XSLT = "static/DataciteToISO19139v3.2.xslt"
ISOXML_SCRIPT = "bin/makeISOXMLFile.py"
PYTHON = "/opt/rh/python27/root/usr/bin/python"

config = json.loads(open('config.json', 'r').read())


def connect_to_db():
    info = config['DATABASE']
    conn = psycopg2.connect(host=info['HOST'],
                            port=info['PORT'],
                            database=info['DATABASE'],
                            user=info['USER'],
                            password=info['PASSWORD'])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return (conn, cur)


def submitToEZID(uid):

    datacite_file = getDCXMLFileName(uid)
    # Read in EZID connection details
    with open(EZID_FILE) as ezid_file:
        ezid_details = json.load(ezid_file)

    # Submit the datacite file to EZID to get the DOI
    try:
        opener = urllib2.build_opener(MyHTTPErrorProcessor())
        h = urllib2.HTTPBasicAuthHandler()
        h.add_password("EZID", ezid_details['SERVER'], ezid_details['USER'], ezid_details['PASSWORD'])
        opener.add_handler(h)

        data = formatAnvlRequest(["datacite", "@%s" % datacite_file])
        # if using mint to generate random DOI id:
        # response = issueRequest(ezid_details['SERVER'], opener, "shoulder/%s" % encode(ezid_details['SHOULDER']), "POST", data)
        # if using the create option, rather than mint:
        id = ezid_details['SHOULDER'] + uid

        response = issueRequest(ezid_details['SERVER'], opener, "id/%s" % encode(id), "PUT", data)
        # print("RESPONSE: %s" % response)
        if response == "Error: bad request - unrecognized DOI shoulder\n":
            return("Error: unrecognized DOI shoulder")

        elif "Missing child element" in response:
            return("Error generating DOI: missing required DataCite fields.<br/>" +
                   "Make sure the following are all populated:<br/>Publisher<br/>Year<br/>Resource Type<br/>Title<br/>Author")

        elif "doi" not in response:
            return("Error generating DOI. Returned response from EZID: %s" % response)

        else:
            doi = response.split(" ")[1]
            doi = doi.replace("doi:", "")

            # move xml to landing page directory (need to rename)
            # new_file_name = os.path.join(LANDING['LANDING_DIR'], doi[-6:])
            # cmd = "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null %s %s@%s:%s" %\
            #     (datacite_file, LANDING['REMOTE_USER'], LANDING['REMOTE_HOST'], new_file_name)
            # print(cmd)
            # os.system(cmd.encode('utf-8'))
            os.remove(datacite_file)

            return("Successfully registered dataset at EZID, doi: %s" % doi)

    except urllib2.HTTPError as e:
        return("Error: Failed to authenticate with EZID server")

    except urllib2.URLError as e:
        return("Error connecting to EZID server")

    except Exception as e:
        return("Error generating DOI: %s" % str(e))


def getDataCiteXML(uid):
    print('in getDataCiteXML')
    status = 1
    (conn, cur) = connect_to_db()
    if type(conn) is str:
        out_text = conn
    else:
        # query the database to get the XML for the submission ID
        try:
            sql_cmd = '''SELECT datacitexml FROM generate_datacite_xml WHERE id='%s';''' % uid
            cur.execute(sql_cmd)
            res = cur.fetchone()
            xml = minidom.parseString(res['datacitexml'])
            out_text = xml.toprettyxml().encode('utf-8').strip()
        except:
            out_text = "Error running database query. \n%s" % sys.exc_info()[1][0]
            print(out_text)
            status = 0

    # write the xml to a temporary file
    xml_file = getDCXMLFileName(uid)
    with open(xml_file, "w") as myfile:
        myfile.write(out_text)
    return(xml_file, status)


def getDataCiteXMLFromFile(uid):
    dcxml_file = getDCXMLFileName(uid)
    # check if datacite xml file already exists
    if os.path.exists(dcxml_file):
        try:
            with open(dcxml_file) as infile:
                dcxml = infile.read()
            return dcxml
        except:
            return "Error reading DataCite XML file."
    return "Will be generated after Database import"


def getDCXMLFileName(uid):
    return os.path.join(DCXML_FOLDER, uid + ".xml")


def getISOXMLFromFile(uid):
    isoxml_file = getISOXMLFileName(uid)
    # check if datacite xml file already exists
    if not os.path.exists(isoxml_file):
        msg = doISOXML(uid)
        if msg.find("Error") >= 0:
            return msg
    try:
        with open(isoxml_file) as infile:
            isoxml = infile.read()
        return isoxml
    except:
        return "Error reading ISO XML file."
    return "Will be generated after Database import"


def getISOXMLFileName(uid):
    return os.path.join(ISOXML_FOLDER, "submission-id%siso.xml" % uid)


def isRegisteredWithEZID(uid):
    with open(EZID_FILE) as ezid_file:
        ezid_details = json.load(ezid_file)
    id = ezid_details['SHOULDER'] + uid
    ezid_url = ezid_details['SERVER'] + '/id/' + id
    r = requests.get(ezid_url)
    return r.status_code == 200


def doISOXML(uid):
    # get datacite XML
    xml_filename = getDCXMLFileName(uid)
    if not os.path.exists(xml_filename):
        xml_filename, status = getDataCiteXML(uid)
        if status == 0:
            return "Error obtaining DataCite XML file"

    try:
        # convert to ISO XML by running through xslt
        xsl_filename = DATACITE_TO_ISO_XSLT
        isoxml_filename = getISOXMLFileName(uid)

        # need to run external script as lxml module doesn't seem to work when running with apache
        process = Popen([PYTHON, ISOXML_SCRIPT, xml_filename, xsl_filename, isoxml_filename], stdout=PIPE)
        (output, err) = process.communicate()
        if err:
            return "Error making ISO XML file.  %s" % err
        return output

    except Exception as e:
        return "Error making ISO XML file.  %s" % str(e)


def ISOXMLExists(uid):
    return os.path.exists(getISOXMLFileName(uid))


# def copyISOXMLFile(isoxml_file):
#         ISO = json.loads(open(ISO_WATCHDIR_CONFIG_FILE, 'r').read())
#         new_file_name = os.path.join(ISO['ISO_WATCH_DIR'], isoxml_file.split('/')[-1])
#         cmd = "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null %s %s@%s:%s" %\
#             (isoxml_file, ISO['REMOTE_USER'], ISO['REMOTE_HOST'], new_file_name)
#         print(cmd)
#         return os.system(cmd.encode('utf-8'))
        # os.remove(isoxml_file)


def isCurator():
    if session.get('user_info') is None:
        return False
    userid = session['user_info'].get('id')
    if userid is None:
        userid = session['user_info'].get('orcid')
    curator_file = open(CURATORS_LIST, 'r')
    curators = curator_file.read().split('\n')
    return userid in curators