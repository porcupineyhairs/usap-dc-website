from __future__ import print_function

import sys
reload(sys)
sys.setdefaultencoding("utf-8")

import math
import flask
from flask import Flask, session, render_template, redirect, url_for, request, g, jsonify, flash, send_from_directory, send_file, current_app
from flask_session import Session
import random
from random import randint
from OpenSSL import SSL
import binascii, os
from flask_oauth import OAuth, OAuthException
import json
from urllib2 import Request, urlopen, URLError
import sys
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
import psycopg2
import psycopg2.extras
import requests
import re
import copy
from datetime import datetime
import csv
from collections import namedtuple
import string
import humanize
import urllib
import lib.json2sql as json2sql
import shutil
from lib.curatorFunctions import isCurator, isRegisteredWithEZID, submitToEZID, getDataCiteXML, getDataCiteXMLFromFile, getDCXMLFileName,\
    getISOXMLFromFile, getISOXMLFileName, doISOXML, ISOXMLExists

app = Flask(__name__)


############
# Load configuration
############
app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR="flask_session",
    PERMANENT_SESSION_LIFETIME=86400,
    UPLOAD_FOLDER="upload",
    DATASET_FOLDER="dataset",
    SUBMITTED_FOLDER="submitted",
    SAVE_FOLDER="saved",
    DOCS_FOLDER="doc",
    DOI_REF_FILE="inc/doi_ref",
    DEBUG=True
)

app.config.update(json.loads(open('config.json', 'r').read()))


app.debug = app.config['DEBUG']
app.secret_key = app.config['SECRET_KEY']

oauth = OAuth()
google = oauth.remote_app('google',
                          base_url='https://www.google.com/accounts/',
                          authorize_url='https://accounts.google.com/o/oauth2/auth',
                          request_token_url=None,
                          request_token_params={'scope': 'https://www.googleapis.com/auth/userinfo.email',
                                                'response_type': 'code'},
                          access_token_url='https://accounts.google.com/o/oauth2/token',
                          access_token_method='POST',
                          access_token_params={'grant_type': 'authorization_code'},
                          consumer_key=app.config['GOOGLE_CLIENT_ID'],
                          consumer_secret=app.config['GOOGLE_CLIENT_SECRET'])


orcid = oauth.remote_app('orcid',
                         base_url='https://orcid.org/oauth/',
                         authorize_url='https://orcid.org/oauth/authorize',
                         request_token_url=None,
                         request_token_params={'scope': '/authenticate',
                                               'response_type': 'code',
                                               'show_login': 'true'},
                         access_token_url='https://pub.orcid.org/oauth/token',
                         access_token_method='POST',
                         access_token_params={'grant_type': 'authorization_code'},
                         consumer_key=app.config['ORCID_CLIENT_ID'],
                         consumer_secret=app.config['ORCID_CLIENT_SECRET'])

config = json.loads(open('config.json', 'r').read())

def connect_to_db():
    info = config['DATABASE']
    conn = psycopg2.connect(host=info['HOST'],
                            port=info['PORT'],
                            database=info['DATABASE'],
                            user=info['USER'],
                            password=info['PASSWORD'])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return (conn,cur)

def get_nsf_grants(columns, award=None, only_inhabited=True):
    (conn,cur) = connect_to_db()
    query_string = 'SELECT %s FROM award a WHERE a.award != \'XXXXXXX\' and a.award::integer<1700000 and a.award::integer>0400000' % ','.join(columns)
    
    if only_inhabited:
        query_string += ' AND EXISTS (SELECT award_id FROM dataset_award_map dam WHERE dam.award_id=a.award)'
    query_string +=  ' ORDER BY name,award'
    cur.execute(query_string)
    return cur.fetchall()

def filter_datasets(dataset_id=None, award=None, parameter=None, location=None, person=None, platform=None,
                    sensor=None, west=None,east=None,south=None,north=None, spatial_bounds=None, spatial_bounds_interpolated=None,start=None, stop=None, program=None,
                    project=None, title=None, limit=None, offset=None):
    (conn,cur) = connect_to_db()
    query_string = '''SELECT DISTINCT d.id
                      FROM dataset d
                      LEFT JOIN dataset_award_map dam ON dam.dataset_id=d.id
                      LEFT JOIN award a ON a.award = dam.award_id
                      LEFT JOIN dataset_keyword_map dkm ON dkm.dataset_id=d.id
                      LEFT JOIN keyword k ON k.id=dkm.keyword_id
                      LEFT JOIN dataset_parameter_map dparm ON dparm.dataset_id=d.id
                      LEFT JOIN parameter par ON par.id=dparm.parameter_id
                      LEFT JOIN dataset_location_map dlm ON dlm.dataset_id=d.id
                      LEFT JOIN location l ON l.id=dlm.location_id
                      LEFT JOIN dataset_person_map dperm ON dperm.dataset_id=d.id
                      LEFT JOIN person per ON per.id=dperm.person_id
                      LEFT JOIN dataset_platform_map dplm ON dplm.dataset_id=d.id
                      LEFT JOIN platform pl ON pl.id=dplm.platform_id
                      LEFT JOIN dataset_sensor_map dsenm ON dsenm.dataset_id=d.id
                      LEFT JOIN sensor sen ON sen.id=dsenm.sensor_id
                      LEFT JOIN dataset_spatial_map sp ON sp.dataset_id=d.id
                      LEFT JOIN dataset_temporal_map tem ON tem.dataset_id=d.id
                      LEFT JOIN award_program_map apm ON apm.award_id=a.award
                      LEFT JOIN program prog ON prog.id=apm.program_id
                      LEFT JOIN dataset_initiative_map dprojm ON dprojm.dataset_id=d.id
                      LEFT JOIN initiative proj ON proj.id=dprojm.initiative_id
                   '''
    conds = []
    if dataset_id:
        conds.append(cur.mogrify('d.id=%s',(dataset_id,)))
    if title:
        conds.append(cur.mogrify('d.title ILIKE %s',('%'+title+'%',)))
    if award:
        [num, name] = award.split(' ',1)
        conds.append(cur.mogrify('a.award=%s',(num,)))
        conds.append(cur.mogrify('a.name=%s',(name,)))
    if parameter:
        conds.append(cur.mogrify('par.id ILIKE %s',('%'+parameter+'%',)))
    if location:
        conds.append(cur.mogrify('l.id=%s',(location,)))
    if person:
        conds.append(cur.mogrify('per.id=%s',(person,)))
    if platform:
        conds.append(cur.mogrify('pl.id=%s',(platform,)))
    if sensor:
        conds.append(cur.mogrify('sen.id=%s',(sensor,)))
    if west:
        conds.append(cur.mogrify('%s <= sp.east', (west,)))
    if east:
        conds.append(cur.mogrify('%s >= sp.west', (east,)))
    if north:
        conds.append(cur.mogrify('%s >= sp.south', (north,)))
    if south:
        conds.append(cur.mogrify('%s <= sp.north', (south,)))
    if spatial_bounds_interpolated:
        conds.append(cur.mogrify("st_intersects(st_transform(sp.bounds_geometry,3031),st_geomfromewkt('srid=3031;'||%s))",(spatial_bounds_interpolated,)))
    if start:
        conds.append(cur.mogrify('%s <= tem.stop_date', (start,)))
    if stop:
        conds.append(cur.mogrify('%s >= tem.start_date', (stop,)))
    if program:
        conds.append(cur.mogrify('prog.id=%s ', (program,)))
    if project:
        conds.append(cur.mogrify('proj.id=%s ', (project,)))
    conds.append(cur.mogrify('url IS NOT NULL '))
    conds = ['(' + c + ')' for c in conds]
    if len(conds) > 0:
        query_string += ' WHERE ' + ' AND '.join(conds)

    cur.execute(query_string)
    return [d['id'] for d in cur.fetchall()]

def get_datasets(dataset_ids):
    if len(dataset_ids) == 0:
        return []
    else:
        (conn,cur) = connect_to_db()
        query_string = \
                   cur.mogrify(
                       '''SELECT d.*,
                             CASE WHEN a.awards IS NULL THEN '[]'::json ELSE a.awards END,
                             CASE WHEN par.parameters IS NULL THEN '[]'::json ELSE par.parameters END,
                             CASE WHEN l.locations IS NULL THEN '[]'::json ELSE l.locations END,
                             CASE WHEN per.persons IS NULL THEN '[]'::json ELSE per.persons END,
                             CASE WHEN pl.platforms IS NULL THEN '[]'::json ELSE pl.platforms END,
                             CASE WHEN sen.sensors IS NULL THEN '[]'::json ELSE sen.sensors END,
                             CASE WHEN ref.references IS NULL THEN '[]'::json ELSE ref.references END,
                             CASE WHEN sp.spatial_extents IS NULL THEN '[]'::json ELSE sp.spatial_extents END,
                             CASE WHEN tem.temporal_extents IS NULL THEN '[]'::json ELSE tem.temporal_extents END,
                             CASE WHEN prog.programs IS NULL THEN '[]'::json ELSE prog.programs END,
                             CASE WHEN proj.projects IS NULL THEN '[]'::json ELSE proj.projects END,
                             CASE WHEN dif.dif_records IS NULL THEN '[]'::json ELSE dif.dif_records END
                       FROM
                        dataset d
                        LEFT JOIN (
                            SELECT dam.dataset_id, json_agg(a) awards
                            FROM dataset_award_map dam JOIN award a ON (a.award=dam.award_id)
                            WHERE a.award != 'XXXXXXX'
                            GROUP BY dam.dataset_id
                        ) a ON (d.id = a.dataset_id)
                        LEFT JOIN (
                            SELECT dkm.dataset_id, json_agg(k) keywords
                            FROM dataset_keyword_map dkm JOIN keyword k ON (k.id=dkm.keyword_id)
                            GROUP BY dkm.dataset_id
                        ) k ON (d.id = k.dataset_id)
                        LEFT JOIN (
                            SELECT dparm.dataset_id, json_agg(par) parameters
                            FROM dataset_parameter_map dparm JOIN parameter par ON (par.id=dparm.parameter_id)
                            GROUP BY dparm.dataset_id
                        ) par ON (d.id = par.dataset_id)
                        LEFT JOIN (
                            SELECT dlm.dataset_id, json_agg(l) locations
                            FROM dataset_location_map dlm JOIN location l ON (l.id=dlm.location_id)
                            GROUP BY dlm.dataset_id
                        ) l ON (d.id = l.dataset_id)
                        LEFT JOIN (
                            SELECT dperm.dataset_id, json_agg(per) persons
                            FROM dataset_person_map dperm JOIN person per ON (per.id=dperm.person_id)
                            GROUP BY dperm.dataset_id
                        ) per ON (d.id = per.dataset_id)
                        LEFT JOIN (
                            SELECT dplm.dataset_id, json_agg(pl) platforms
                            FROM dataset_platform_map dplm JOIN platform pl ON (pl.id=dplm.platform_id)
                            GROUP BY dplm.dataset_id
                        ) pl ON (d.id = pl.dataset_id)
                        LEFT JOIN (
                            SELECT dsenm.dataset_id, json_agg(sen) sensors
                            FROM dataset_sensor_map dsenm JOIN sensor sen ON (sen.id=dsenm.sensor_id)
                            GROUP BY dsenm.dataset_id
                        ) sen ON (d.id = sen.dataset_id)
                        LEFT JOIN (
                            SELECT ref.dataset_id, json_agg(ref) AS references
                            FROM dataset_reference_map ref
                            GROUP BY ref.dataset_id
                        ) ref ON (d.id = ref.dataset_id)
                        LEFT JOIN (
                            SELECT sp.dataset_id, json_agg(sp) spatial_extents
                            FROM dataset_spatial_map sp
                            GROUP BY sp.dataset_id
                        ) sp ON (d.id = sp.dataset_id)
                        LEFT JOIN (
                            SELECT tem.dataset_id, json_agg(tem) temporal_extents
                            FROM dataset_temporal_map tem
                            GROUP BY tem.dataset_id
                        ) tem ON (d.id = tem.dataset_id)
                        LEFT JOIN (
                            SELECT dam.dataset_id, json_agg(prog) programs
                            FROM dataset_award_map dam, award_program_map apm, program prog
                            WHERE dam.award_id = apm.award_id AND apm.program_id = prog.id
                            GROUP BY dam.dataset_id
                        ) prog ON (d.id = prog.dataset_id)
                        LEFT JOIN (
                            SELECT dprojm.dataset_id, json_agg(proj) projects
                            FROM dataset_initiative_map dprojm JOIN initiative proj ON (proj.id=dprojm.initiative_id)
                            GROUP BY dprojm.dataset_id
                        ) proj ON (d.id = proj.dataset_id)
                        LEFT JOIN (
                            SELECT ddm.dataset_id, json_agg(dif) dif_records
                            FROM dataset_dif_map ddm JOIN dif ON (dif.dif_id=ddm.dif_id)
                            GROUP BY ddm.dataset_id
                        ) dif ON (d.id = dif.dataset_id)
                        WHERE d.id IN %s ORDER BY d.title''',
                       (tuple(dataset_ids),))
        cur.execute(query_string)
        return cur.fetchall()

# def get_dataset_old(dataset_id):
#     (conn, cur) = connect_to_db()
#     data = dict()
#     cur.execute('SELECT * FROM dataset d WHERE id=%s', (dataset_id,))
#     data.update(cur.fetchall()[0])
#     data['keywords'] = get_keywords(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['parameters'] = get_parameters(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['locations'] = get_locations(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['persons'] = get_persons(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['sensors'] = get_sensors(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['references'] = get_references(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['spatial_extents'] = get_spatial_extents(conn=conn, cur=cur, dataset_id=dataset_id)
#     data['temporal_extents'] = get_temporal_extents(conn=conn, cur=cur, dataset_id=dataset_id)
#     return data
    
def get_parameter_menu(conn=None, cur=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    cur.execute('SELECT terms FROM parameter_menu_orig')
    return cur.fetchall()

def get_location_menu(conn=None, cur=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    cur.execute('SELECT * FROM location_menu')
    return cur.fetchall()

def get_parameters(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT DISTINCT parameter_id AS id FROM dataset_parameter_map'
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_titles(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT DISTINCT title FROM dataset ORDER BY title'
    cur.execute(query)
    return cur.fetchall()

def get_locations(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT DISTINCT location_id AS id FROM dataset_location_map'
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_keywords(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM keyword'
    if dataset_id:
        query += cur.mogrify(' WHERE id in (SELECT keyword_id FROM dataset_keyword_map WHERE dataset_id=%s)', (dataset_id,))
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_platforms(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM platform'
    if dataset_id:
        query += cur.mogrify(' WHERE id in (SELECT platform_id FROM dataset_platform_map WHERE dataset_id=%s)', (dataset_id,))
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_persons(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM person'
    if dataset_id:
        query += cur.mogrify(' WHERE id in (SELECT person_id FROM dataset_person_map WHERE dataset_id=%s)', (dataset_id,))
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_sensors(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM sensor'
    if dataset_id:
        query += cur.mogrify(' WHERE id in (SELECT sensor_id FROM dataset_sensor_map WHERE dataset_id=%s)', (dataset_id,))
    query += cur.mogrify(' ORDER BY id')
    cur.execute(query)
    return cur.fetchall()

def get_references(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM dataset_reference_map'
    if dataset_id:
        query += cur.mogrify(' WHERE dataset_id=%s', (dataset_id,))
    cur.execute(query)
    return cur.fetchall()

def get_spatial_extents(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM dataset_spatial_map'
    if dataset_id:
        query += cur.mogrify(' WHERE dataset_id=%s', (dataset_id,))
    cur.execute(query)
    return cur.fetchall()


def get_temporal_extents(conn=None, cur=None, dataset_id=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM dataset_temporal_map'
    if dataset_id:
        query += cur.mogrify(' WHERE dataset_id=%s', (dataset_id,))
    cur.execute(query)
    return cur.fetchall()


def get_programs(conn=None, cur=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM program'
    cur.execute(query)
    return cur.fetchall()


def get_projects(conn=None, cur=None):
    if not (conn and cur):
        (conn, cur) = connect_to_db()
    query = 'SELECT * FROM initiative'
    cur.execute(query)
    return cur.fetchall()


@app.route('/submit/dataset', methods=['GET', 'POST'])
def dataset():
    error = ''
    success = ''
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/submit/dataset'
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'dataset_metadata' not in session:
            session['dataset_metadata'] = dict()
        session['dataset_metadata'].update(request.form.to_dict())

        publications_keys = [s for s in request.form.keys() if "publication" in s]
        remove_pub_keys = []
        if len(publications_keys) > 0:
            publications_keys.sort()
            print(publications_keys)
            #remove any empty values
            for key in publications_keys:
                if session['dataset_metadata'][key] == "":
                    del session['dataset_metadata'][key]
                    remove_pub_keys.append(key)
            for k in remove_pub_keys: 
                publications_keys.remove(k)
            print(publications_keys)
            session['dataset_metadata']['publications'] = [request.form.get(key) for key in publications_keys]

        session['dataset_metadata']['agree'] = 'agree' in request.form
        flash('test message')

        if request.form.get('action') == "Previous Page":
            return render_template('dataset.html', name=user_info['name'], email="", error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()), nsf_grants=get_nsf_grants(['award', 'name', 'title'], only_inhabited=False), projects=get_projects())

        elif request.form.get('action') == "save":
            # save to file
            if user_info.get('orcid'):
                save_file = os.path.join(app.config['SAVE_FOLDER'], user_info['orcid'] + ".json")
            elif user_info.get('id'):
                save_file = os.path.join(app.config['SAVE_FOLDER'], user_info['id'] + ".json")
            else:
                error = "Unable to save dataset."
            if save_file:
                try:
                    with open(save_file, 'w') as file:
                        file.write(json.dumps(session.get('dataset_metadata', dict()), indent=4, sort_keys=True))
                    success = "Saved dataset form"
                except Exception as e:
                    error = "Unable to save dataset."
            return render_template('dataset.html', name=user_info['name'], email="", error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()), nsf_grants=get_nsf_grants(['award', 'name', 'title'], only_inhabited=False), projects=get_projects())

        elif request.form.get('action') == "restore":
            # restore from file
            if user_info.get('orcid'):
                saved_file = os.path.join(app.config['SAVE_FOLDER'], user_info['orcid'] + ".json")
            elif user_info.get('id'):
                saved_file = os.path.join(app.config['SAVE_FOLDER'], user_info['id'] + ".json")
            else:
                error = "Unable to restore dataset"
            if saved_file:
                try:
                    with open(saved_file, 'r') as file:
                        data = json.load(file)
                    session['dataset_metadata'].update(data)
                    success = "Restored dataset form"
                except Exception as e:
                    error = "Unable to restore dataset."
            else:
                error = "Unable to restore dataset."
            return render_template('dataset.html', name=user_info['name'], email="", error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()), nsf_grants=get_nsf_grants(['award', 'name', 'title'], only_inhabited=False), projects=get_projects())

        return redirect('/submit/dataset2')

    else:
        email = ""
        if user_info.get('email'):
            email = user_info.get('email')
        name = ""
        if user_info.get('name'):
            email = user_info.get('name')
        return render_template('dataset.html', name=name, email=email, error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()), nsf_grants=get_nsf_grants(['award', 'name', 'title'], only_inhabited=False), projects=get_projects())


@app.route('/submit/help', methods=['GET', 'POST'])
def submit_help():
    return render_template('submission_help.html')


class ExceptionWithRedirect(Exception):
    def __init__(self, message, redirect):
        self.redirect = redirect
        super(ExceptionWithRedirect, self).__init__(message)
    
class BadSubmission(ExceptionWithRedirect):
    pass
        
class CaptchaException(ExceptionWithRedirect):
    pass

class InvalidDatasetException(ExceptionWithRedirect):
    def __init__(self,msg='Invalid Dataset#',redirect='/'):
        super(InvalidDatasetException, self).__init__(msg,redirect)


@app.errorhandler(CaptchaException)
def failed_captcha(e):
    return render_template('error.html',error_message=str(e))


@app.errorhandler(BadSubmission)
def invalid_dataset(e):
    return render_template('error.html',error_message=str(e),back_url=e.redirect,name=session['user_info']['name'])


#@app.errorhandler(OAuthException)
def oauth_error(e):
    return render_template('error.html',error_message=str(e))


#@app.errorhandler(Exception)
def general_error(e):
    return render_template('error.html',error_message=str(e))


#@app.errorhandler(InvalidDatasetException)
def view_error(e):
    return render_template('error.html',error_message=str(e))


@app.route('/thank_you/<submission_type>')
def thank_you(submission_type):
    return render_template('thank_you.html',submission_type=submission_type)


Validator = namedtuple('Validator', ['func', 'msg'])

def check_dataset_submission(msg_data):
    print(msg_data, file=sys.stderr)
    def default_func(field):
        return lambda data: field in data and bool(data[field]) and data[field] != "None"
    def check_spatial_bounds(data):
        if not(data['geo_e'] or data['geo_w'] or data['geo_s'] or data['geo_n']):
            return True
        else:
            try:
                return \
                    abs(float(data['geo_w'])) <= 180 and \
                    abs(float(data['geo_e'])) <= 180 and \
                    abs(float(data['geo_n'])) >= -90 and abs(float(data['geo_s'])) >= -90
            except:
                return False
    
    validators = [
        Validator(func=default_func('title'),msg='You must include a dataset title for the submission.'),
        Validator(func=default_func('author'),msg='You must include a dataset author for the submission.'),
        Validator(func=default_func('email'),msg='You must include a contact email address for the submission.'),
        Validator(func=default_func('award'),msg='You must select an NSF grant for the submission.'),
        Validator(func=check_spatial_bounds, msg="Spatial bounds are invalid."),
        Validator(func=default_func('filenames'),msg='You must include files in your submission.'),
        Validator(func=default_func('agree'),msg='You must agree to have your files posted with a DOI.')
    ]
    msg = ""
    for v in validators:
        if not v.func(msg_data):
            msg += "<p>" + v.msg
    if len(msg) > 0:
        raise BadSubmission(msg,'/submit/dataset')

@app.route('/repo_list')
def repo_list():
    return render_template('repo_list.html')


@app.route('/not_found')
def not_found():
    return render_template('not_found.html')


def check_project_registration(msg_data):
    def default_func(field):
        return lambda data: field in data and bool(data[field])
    
    validators = [
        Validator(func=default_func('award'),msg="You must select an award #"),
        Validator(func=default_func("title"),msg="You must provide a title for the project"),
        Validator(func=default_func("name"),msg="You must provide the PI's name for the project"),
        Validator(func=default_func('email'),msg='You must include a contact email address for the submission.'),
        Validator(func=lambda data: 'repos' in data and (len(data['repos'])>0 or data['repos'] == 'nodata'),msg="You must provide info about the repository where you submitted the dataset"),
        Validator(func=lambda data: 'locations' in data and len(data['locations'])>0,msg="You must provide at least one location term"),
        Validator(func=lambda data: 'parameters' in data and len(data['parameters'])>0,msg="You must provide at least one keyword term")
    ]
    msg = ""
    for v in validators:
        if not v.func(msg_data):
            msg += "<p>" + v.msg
    if len(msg) > 0:
        raise BadSubmission(msg,'/submit/project')
    

def format_time():
    t = datetime.utcnow()
    s = t.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return s[:-5] + 'Z'
        
@app.route('/submit/dataset2',methods=['GET','POST'])
def dataset2():
    error = ""
    success = ""
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/submit/dataset2'

    if request.method == 'POST':
        if 'dataset_metadata' not in session:
            session['dataset_metadata'] = dict()

        session['dataset_metadata'].update(request.form.to_dict())
        session['dataset_metadata']['properGeoreferences'] = 'properGeoreferences' in request.form
        session['dataset_metadata']['propertiesExplained'] = 'propertiesExplained' in request.form
        session['dataset_metadata']['comprehensiveLegends'] = 'comprehensiveLegends' in request.form
        session['dataset_metadata']['dataUnits'] = 'dataUnits' in request.form

        if request.form.get('action') == 'Submit':
            msg_data = copy.copy(session['dataset_metadata'])
            msg_data['name'] = session['user_info']['name']
            del msg_data['action']

            cross_dateline = False
            if session['dataset_metadata'].get('cross_dateline') == 'on':
                cross_dateline = True
            msg_data['cross_dateline'] = cross_dateline

            if 'orcid' in session['user_info']:
                msg_data['orcid'] = session['user_info']['orcid']

            files = request.files.getlist('file[]')
            fnames = dict()
            for f in files:
                fname = secure_filename(f.filename)
                if len(fname) > 0:
                    fnames[fname] = f

            msg_data['filenames'] = fnames.keys()
            timestamp = format_time()
            msg_data['timestamp'] = timestamp
            check_dataset_submission(msg_data)

            nsfid = 'NSF' + msg_data['award'].split(' ')[0]
            upload_dir = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'], timestamp)
            msg_data['upload_directory'] = upload_dir
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)

            for fname, fobj in fnames.items():
                fobj.save(os.path.join(upload_dir, fname))

            
            # save json file in submitted dir
            submitted_dir = os.path.join(current_app.root_path, app.config['SUBMITTED_FOLDER'])
            # get next_id
            next_id = getNextDOIRef()
            updateNextDOIRef()
            submitted_file = os.path.join(submitted_dir, next_id + ".json")
            with open(submitted_file, 'w') as file:
                file.write(json.dumps(msg_data, indent=4, sort_keys=True))
            os.chmod(submitted_file, 0o664)


            """
            # email RT queue
            # msg = MIMEText(json.dumps(msg_data, indent=4, sort_keys=True))
            message = "New dataset submission.\n\nDataset JSON: %scurator?uid=%s\n" \
                % (request.url_root, next_id)
            msg = MIMEText(message)
            sender = msg_data.get('email')
            recipients = ['info@usap-dc.org']
       
            msg['Subject'] = 'USAP-DC Dataset Submission'
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)

            smtp_details = config['SMTP']
            s = smtplib.SMTP(smtp_details["SERVER"], smtp_details['PORT'].encode('utf-8'))
            # identify ourselves to smtp client
            s.ehlo()
            # secure our email with tls encryption
            s.starttls()
            # re-identify ourselves as an encrypted connection
            s.ehlo()
            s.login(smtp_details["USER"], smtp_details["PASSWORD"])
            s.sendmail(sender, recipients, msg.as_string())
            s.quit()
            """

            return redirect('/thank_you/dataset')
        elif request.form['action'] == 'Previous Page':
            # post the form back to dataset since the session['dataset_metadata'] 
            # gets lost if we use a standard GET redirect
            print('DATASET2b, publications: %s' % session['dataset_metadata'].get('publications'))
            return redirect('/submit/dataset', code=307)
        elif request.form.get('action') == "save":
            # save to file
            if user_info.get('orcid'):
                save_file = os.path.join(app.config['SAVE_FOLDER'], user_info['orcid'] + ".json")
            elif user_info.get('id'):
                save_file = os.path.join(app.config['SAVE_FOLDER'], user_info['id'] + ".json")
            else:
                error = "Unable to save dataset."
            if save_file:
                try:
                    with open(save_file, 'w') as file:
                        file.write(json.dumps(session.get('dataset_metadata', dict()), indent=4, sort_keys=True))
                    success = "Saved dataset form"
                except Exception as e:
                    error = "Unable to save dataset."
            return render_template('dataset2.html', name=user_info['name'], email="", error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()))

        elif request.form.get('action') == "restore":
            # restore from file
            if user_info.get('orcid'):
                saved_file = os.path.join(app.config['SAVE_FOLDER'], user_info['orcid'] + ".json")
            elif user_info.get('id'):
                saved_file = os.path.join(app.config['SAVE_FOLDER'], user_info['id'] + ".json")
            else:
                error = "Unable to restore dataset"
            if saved_file:
                try:
                    with open(saved_file, 'r') as file:
                        data = json.load(file)
                    session['dataset_metadata'].update(data)
                    success = "Restored dataset form"
                except Exception as e:
                    error = "Unable to restore dataset."
            else:
                error = "Unable to restore dataset."
            return render_template('dataset2.html', name=user_info['name'], email="", error=error, success=success, dataset_metadata=session.get('dataset_metadata', dict()))

    else:
        email = ""
        if user_info.get('email'):
            email = user_info.get('email')
        name = ""
        if user_info.get('name'):
            email = user_info.get('name')
        return render_template('dataset2.html', name=name, email=email, dataset_metadata=session.get('dataset_metadata', dict()))


# Read the next doi reference number from the file
def getNextDOIRef():
    return open(app.config['DOI_REF_FILE'], 'r').readline().strip()


# increment the next email reference number in the file
def updateNextDOIRef():
    newRef = int(getNextDOIRef()) + 1
    with open(app.config['DOI_REF_FILE'], 'w') as refFile:
        refFile.write(str(newRef))


@app.route('/submit/project',methods=['GET','POST'])
def project():
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/submit/project'
        return redirect(url_for('login'))

    if request.method == 'POST':
        msg_data = dict()
        msg_data['name'] = session['user_info']['name']
        if 'orcid' in session['user_info']:
            msg_data['orcid'] = session['user_info']['orcid']
        # if 'email' in session['user_info']:
        #     msg_data['email'] = session['user_info']['email']
        msg_data.update(request.form.to_dict())

        parameters = []
        idx = 1
        key = 'parameter1'
        while key in msg_data:
            parameters.append(msg_data[key])
            del msg_data[key]
            idx += 1
            key = 'parameter'+str(idx)
        msg_data['parameters'] = parameters

        locations = []
        idx = 1
        key = 'location1'
        while key in msg_data:
            locations.append(msg_data[key])
            del msg_data[key]
            idx += 1
            key = 'location'+str(idx)
        msg_data['locations'] = locations

        if 'nodata' in msg_data:
            repos = 'nodata'
            del msg_data['nodata']
        else:
            repos = []
            idx = 1
            key = 'repo1'
            while key in msg_data:
                if msg_data[key] == 'USAP-DC':
                    repos.append({'name':'USAP-DC'})
                else:
                    d = dict()
                    if 'repo_other_name'+str(idx) in msg_data:
                        d['name'] = msg_data['repo_other_name'+str(idx)]
                    if 'repo_other_id'+str(idx) in msg_data:
                        d['id'] = msg_data['repo_other_id'+str(idx)]
                    repos.append(d)
                idx+=1
                key = 'repo'+str(idx)
        msg_data = {k:v for k,v in msg_data.iteritems() if k[:4] != 'repo'}   
        msg_data['repos'] = repos

        msg_data['timestamp'] = format_time()
        msg = MIMEText(json.dumps(msg_data, indent=4, sort_keys=True))
        check_project_registration(msg_data)

        sender = msg_data.get('email')
        recipients = ['info@usap-dc.org']
        msg['Subject'] = 'USAP-DC Project Submission'
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)

        smtp_details = config['SMTP']
        """
        s = smtplib.SMTP(smtp_details["SERVER"], smtp_details['PORT'].encode('utf-8'))
        # identify ourselves to smtp client
        s.ehlo()
        # secure our email with tls encryption
        s.starttls()
        # re-identify ourselves as an encrypted connection
        s.ehlo()
        s.login(smtp_details["USER"], smtp_details["PASSWORD"])
        s.sendmail(sender, recipients, msg.as_string())
        s.quit()
        """

        return redirect('thank_you/project')
    else:
        email = ""
        if user_info.get('email'):
            email = user_info.get('email')
        return render_template('project.html',name=user_info['name'],email=email,nsf_grants=get_nsf_grants(['award','name'],only_inhabited=False), locations=get_location_menu(), parameters=get_parameter_menu())


@app.route('/submit/projectinfo',methods=['GET'])
def projectinfo():
    award_id = request.args.get('award')
    if award_id is not None:       
        (conn, cur) = connect_to_db()
        query_string = "SELECT * FROM award a WHERE a.award = '%s'" % award_id
        cur.execute(query_string)
        return flask.jsonify(cur.fetchall()[0])
    return flask.jsonify({})


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login_google')
def login_google():
    callback = url_for('authorized', _external=True)
    return google.authorize(callback=callback)


@app.route('/login_orcid')
def login_orcid():
    callback = url_for('authorized_orcid', _external=True)
    return orcid.authorize(callback=callback)


@app.route('/authorized')
@google.authorized_handler
def authorized(resp):
    access_token = resp['access_token']
    session['google_access_token'] = access_token, ''
    session['googleSignedIn'] = True
    headers = {'Authorization': 'OAuth '+access_token}
    req = Request('https://www.googleapis.com/oauth2/v1/userinfo',
                  None, headers)
    res = urlopen(req)
    session['user_info'] = json.loads(res.read())
    print(session['user_info'])
    return redirect(session['next'])


@app.route('/authorized_orcid')
@orcid.authorized_handler
def authorized_orcid(resp):
    session['orcid_access_token'] = resp['access_token']
    session['user_info'] = {
        'name': resp.get('name'),
        'orcid': resp.get('orcid')
    }
    return redirect(session['next'])


@google.tokengetter
def get_access_token():
    return session.get('google_access_token')


@app.route('/logout', methods=['GET'])
def logout():
    if 'user_info' in session:
        del session['user_info']
    if 'google_access_token' in session:
        del session['google_access_token']
    if 'orcid_access_token' in session:
        del session['orcid_access_token']
    if 'dataset_metadata' in session:
        del session['dataset_metadata']
    if request.args.get('type') == 'curator':
        return redirect(url_for('curator'))
    return redirect(url_for('submit'))


@app.route("/index", methods=['GET'])
@app.route("/", methods=['GET'])
@app.route("/home", methods=['GET'])
def home():
    template_dict = {}

    if request.method == 'GET':
        if request.args.get('google') == 'false':
            session['googleSignedIn'] = False

    # read in news
    news_dict = []
    with open("inc/recent_news.txt") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        for row in reader:
            if row[0] == "#" or len(row) < 2: continue
            news_dict.append({"date": row[0], "news": row[1]})
        template_dict['news_dict'] = news_dict
    # read in recent data
    data_dict = []
    with open("inc/recent_data.txt") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        for row in reader:
            if row[0] == "#" or len(row) < 4: continue
            data_dict.append({"date": row[0], "link": row[1], "authors": row[2], "title": row[3]})
        template_dict['data_dict'] = data_dict

    # get all spatial extents
    (conn, cur) = connect_to_db()
    template_dict['spatial_extents'] = get_spatial_extents(conn=conn, cur=cur)
    return render_template('home.html', **template_dict)


# @app.route("/home2")
# def home2():
#     template_dict = {}
#     # read in news
#     news_dict = []
#     with open("inc/recent_news.txt") as csvfile:
#         reader = csv.reader(csvfile, delimiter="\t")
#         for row in reader:
#             if row[0] == "#" or len(row) != 2: continue
#             news_dict.append({"date": row[0], "news": row[1]})
#         template_dict['news_dict'] = news_dict
#     # read in recent data
#     data_dict = []
#     with open("inc/recent_data.txt") as csvfile:
#         reader = csv.reader(csvfile, delimiter="\t")
#         for row in reader:
#             if row[0] == "#" or len(row) != 4: continue
#             data_dict.append({"date": row[0], "link": row[1], "authors": row[2], "title": row[3]})
#         template_dict['data_dict'] = data_dict
#     return render_template('home2.html', **template_dict)


@app.route('/overview')
def overview():
    return render_template('overview.html')


@app.route('/links')
def links():
    return render_template('links.html')


@app.route('/sdls')
def sdls():
    return render_template('sdls.html')


@app.route('/legal')
def legal():
    return render_template('legal.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/terms_of_use')
def terms_of_use():
    return render_template('terms_of_use.html')


@app.route('/title_examples')
def title_examples():
    return render_template('title_examples.html')


@app.route('/abstract_examples')
def abstract_examples():
    return render_template('abstract_examples.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    print('in search')
    if request.method == 'GET':
        return render_template('search.html', search_params=session.get('search_params'), nsf_grants=get_nsf_grants(['award', 'name', 'title']), keywords=get_keywords(),
                               parameters=get_parameters(), locations=get_locations(), platforms=get_platforms(),
                               persons=get_persons(), sensors=get_sensors(), programs=get_programs(), projects=get_projects(), titles=get_titles())
    elif request.method == 'POST':
        params = request.form.to_dict()
        print(params)
        filtered = filter_datasets(**params)

        del params['spatial_bounds_interpolated']
        session['filtered_datasets'] = filtered
        session['search_params'] = params

        return redirect('/search_result')


@app.route('/filter_search_menus', methods=['GET'])
def filter_search_menus():
    keys = ['person', 'parameter', 'program', 'award', 'title', 'project']
    args = request.args.to_dict()
    # if reseting:
    if args == {}:
        session['search_params'] = {}

    person_ids = filter_datasets(**{k: args.get(k) for k in keys if k != 'person'})
    person_dsets = get_datasets(person_ids)
    persons = set([p['id'] for d in person_dsets for p in d['persons']])

    parameter_ids = filter_datasets(**{k: args.get(k) for k in keys if k != 'parameter'})
    parameter_dsets = get_datasets(parameter_ids)
    parameters = set([' > '.join(p['id'].split(' > ')[2:]) for d in parameter_dsets for p in d['parameters']])

    program_ids = filter_datasets(**{k: args.get(k) for k in keys if k != 'program'})
    program_dsets = get_datasets(program_ids)
    programs = set([p['id'] for d in program_dsets for p in d['programs']])

    award_ids = filter_datasets(**{k: args.get(k) for k in keys if k != 'award'})
    award_dsets = get_datasets(award_ids)
    awards = set([(p['name'], p['award']) for d in award_dsets for p in d['awards']])

    project_ids = filter_datasets(**{k: args.get(k) for k in keys if k != 'project'})
    project_dsets = get_datasets(project_ids)
    projects = set([p['id'] for d in project_dsets for p in d['projects']])
#    projects = set([d['id'] for d in project_dsets])

    return flask.jsonify({
        'person': sorted(persons),
        'parameter': sorted(parameters),
        'program': sorted(programs),
        'award': [a[1] + ' ' + a[0] for a in sorted(awards)],
        'project': sorted(projects)
    })


@app.route('/search_result', methods=['GET', 'POST'])
def search_result():
    if 'filtered_datasets' not in session:
        return redirect('/search')
    filtered_ids = session['filtered_datasets']
    
    exclude = False
    if request.method == 'POST':
        exclude = request.form.get('exclude') == "on"

    datasets = get_datasets(filtered_ids)

    grp_size = 50
    dataset_grps = []
    cur_grp = []
    total_count = 0
    for d in datasets:
        if exclude and d.get('spatial_extents') and len(d.get('spatial_extents')) > 0 and \
            ((d.get('spatial_extents')[0].get('east') == 180 and d.get('spatial_extents')[0].get('west') == -180) or \
            (d.get('spatial_extents')[0].get('east') == 360 and d.get('spatial_extents')[0].get('west') == 0)):
            continue
        if len(cur_grp) < grp_size:
            cur_grp.append(d)
        else:
            dataset_grps.append(cur_grp)
            cur_grp = []
        total_count += 1
    if len(cur_grp) > 0:
        dataset_grps.append(cur_grp)
    
    return render_template('search_result.html',
                                      total_count=total_count,
                                      dataset_grps=dataset_grps,
                                      exclude=exclude,
                                      search_params=session['search_params'])


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('contact.html',secret=app.config['RECAPTCHA_DATA_SITE_KEY'])
    elif request.method == 'POST':
        form = request.form.to_dict()
        g_recaptcha_response = form.get('g-recaptcha-response')
        remoteip = request.remote_addr
        resp = requests.post('https://www.google.com/recaptcha/api/siteverify', data={'response':g_recaptcha_response,'remoteip':remoteip,'secret': app.config['RECAPTCHA_SECRET_KEY']}).json()
        if resp.get('success'):
            sender = form['email']
            recipients = ['info@usap-dc.org']
            msg = MIMEText(form['msg'])
            msg['Subject'] = form['subj']
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            smtp_details = config['SMTP']
            s = smtplib.SMTP(smtp_details["SERVER"], smtp_details['PORT'].encode('utf-8'))
            # identify ourselves to smtp client
            s.ehlo()
            # secure our email with tls encryption
            s.starttls()
            # re-identify ourselves as an encrypted connection
            s.ehlo()
            s.login(smtp_details["USER"], smtp_details["PASSWORD"])
            s.sendmail(sender, recipients, msg.as_string())
            s.quit()
            return redirect('/thank_you/message')
        else:
            msg = "<br/>You failed to pass the captcha<br/>"
            raise CaptchaException(msg, url_for('contact'))


@app.route('/submit', methods=['GET'])
def submit():
    if request.method == 'GET':
        if request.args.get('google') == 'false':
            session['googleSignedIn'] = False
    return render_template('submit.html')


@app.route('/data_repo')
def data_repo():
    return render_template('data_repo.html')


@app.route('/news')
def news():
    template_dict = {}
    # read in news
    news_dict = []
    with open("inc/recent_news.txt") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        for row in reader:
            if row[0] == "#" or len(row) < 2:
                continue
            news_dict.append({"date": row[0], "news": row[1]})
        template_dict['news_dict'] = news_dict

    return render_template('news.html', **template_dict)


@app.route('/data')
def data():
    template_dict = {}
    # read in recent data
    data_dict = []
    with open("inc/recent_data.txt") as csvfile:
        reader = csv.reader(csvfile, delimiter="\t")
        for row in reader:
            if row[0] == "#" or len(row) < 4:
                continue
            data_dict.append({"date": row[0], "link": row[1], "authors": row[2], "title": row[3]})
        template_dict['data_dict'] = data_dict
    return render_template('data.html', **template_dict)


@app.route('/devices')
def devices():
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/devices'
        return redirect(url_for('login'))
    else:
        return render_template('device_examples.html', name=user_info['name'])


@app.route('/procedures')
def procedures():
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/procedures'
        return redirect(url_for('login'))
    else:
        return render_template('procedure_examples.html', name=user_info['name'])


@app.route('/content')
def content():
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/content'
        return redirect(url_for('login'))
    else:
        return render_template('content_examples.html', name=user_info['name'])


@app.route('/files_to_upload')
def files_to_upload():
    user_info = session.get('user_info')
    if user_info is None:
        session['next'] = '/files_to_upload'
        return redirect(url_for('login'))
    else:
        return render_template('files_to_upload_help.html', name=user_info['name'])


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    return str(obj)


@app.route('/view/dataset/<dataset_id>')
def landing_page(dataset_id):
    datasets = get_datasets([dataset_id])
    if len(datasets) == 0:
        return redirect(url_for('not_found'))
    metadata = datasets[0]
    url = metadata['url']
    if not url:
        return redirect(url_for('not_found'))
    usap_domain = 'http://www.usap-dc.org/'
    # print(url)
    if url.startswith(usap_domain):
        directory = os.path.join(current_app.root_path, url[len(usap_domain):])
        # print(directory)
        file_paths = [os.path.join(dp, f) for dp, dn, fn in os.walk(directory) for f in fn]
        omit = set(['readme.txt', '00README.txt', 'index.php', 'index.html', 'data.html'])
        file_paths = [f for f in file_paths if os.path.basename(f) not in omit]
        files = []
        for f_path in file_paths:
            f_size = os.stat(f_path).st_size
            f_name = os.path.basename(f_path)
            f_subpath = f_path[len(directory):]
            files.append({'url': os.path.join(url, f_subpath), 'name': f_name, 'size': humanize.naturalsize(f_size)})
            metadata['files'] = files
        files.sort()
    else:
        metadata['files'] = [{'url': url, 'name': os.path.basename(os.path.normpath(url))}]

    if metadata.get('url_extra'):
        metadata['url_extra'] = os.path.basename(metadata['url_extra'])

    creator_orcid = None

    for p in metadata['persons'] or []:
        if p['id'] == metadata['creator'] and p['id_orcid'] is not None:
            creator_orcid = p['id_orcid']
            break

    references = []
    for ref in metadata.get('references'):
        refs = ref['reference'].replace("<br><br>", "\n\n")
        refs = refs.split("\n\n")
        references.extend(refs)
    metadata['refs'] = references

    return render_template('landing_page.html', data=metadata, creator_orcid=creator_orcid)


@app.route('/dataset/<path:filename>')
def file_download(filename):
    directory = os.path.join(current_app.root_path, app.config['DATASET_FOLDER'])
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/supplement/<dataset_id>')
def supplement(dataset_id):
    (conn, cur) = connect_to_db()
    cur.execute('''SELECT url_extra FROM dataset WHERE id=%s''', (dataset_id,))
    url_extra = cur.fetchall()[0]['url_extra'][1:]
    if url_extra.startswith('/'):
        url_extra = url_extra[1:]
    try:
        return send_file(os.path.join(current_app.root_path, url_extra),
                       as_attachment=True,
                       attachment_filename=os.path.basename(url_extra))
    except:
        return redirect(url_for('not_found'))


@app.route('/mapserver-template.html')
def mapserver_template():
    return render_template('mapserver-template.html')


@app.route('/map')
def map():
    return render_template('data_map.html')


@app.route('/curator', methods=['GET', 'POST'])
def curator():
    template_dict = {}
    template_dict['message'] = []

    # login
    if (not isCurator()):
        session['next'] = request.url
        template_dict['need_login'] = True
    else:
        template_dict['need_login'] = False
        submitted_dir = os.path.join(current_app.root_path, app.config['SUBMITTED_FOLDER'])

        # get list of json files in submission directory
        files = os.listdir(submitted_dir)
        submissions = []
        for f in files:
            if f.find(".json") > 0:
                dataset_id = f.split(".json")[0]
                # if a submission has a landing page, then set the status to Complete, otherwise Pending
                if len(get_datasets([dataset_id])) == 0:
                    status = "Pending"
                    landing_page = ''
                else:
                    landing_page = '/view/dataset/%s' % dataset_id
                    if not isRegisteredWithEZID(dataset_id):
                        status = "Not yet registered with EZID"
                    elif not ISOXMLExists(dataset_id):
                        status = "ISO XML file missing"
                    else:
                        status = "Completed"
                submissions.append({'id': dataset_id, 'status': status, 'landing_page': landing_page})
        submissions.sort(reverse=True)
        template_dict['submissions'] = submissions

        if request.args.get('uid') is not None:
            uid = request.args.get('uid')
            template_dict['uid'] = uid
            submission_file = os.path.join(submitted_dir, uid + ".json")
            template_dict['filename'] = submission_file
            template_dict['sql'] = "Will be generated after you click on Create SQL and Readme in JSON tab."
            template_dict['readme'] = "Will be generated after you click on Create SQL and Readme in JSON tab."
            template_dict['dcxml'] = getDataCiteXMLFromFile(uid)
            template_dict['tab'] = "json"
            if request.method == 'POST':
                template_dict.update(request.form.to_dict())
                # read in json and convert to sql
                if request.form.get('submit') == 'make_sql':
                    json_str = request.form.get('json').encode('utf-8')
                    json_data = json.loads(json_str)
                    template_dict['json'] = json_str
                    sql, readme_file = json2sql.json2sql(json_data, uid)
                    template_dict['sql'] = sql
                    template_dict['readme_file'] = readme_file
                    template_dict['tab'] = "sql"
                    try:
                        with open(readme_file) as infile:
                            readme_text = infile.read()
                    except:
                        template_dict['error'] = "Can't read Read Me file"
                    template_dict['readme'] = readme_text

                # read in sql and submit to the database only
                elif request.form.get('submit') == 'import_to_db':
                    sql_str = request.form.get('sql').encode('utf-8')
                    template_dict['tab'] = "sql"
                    problem = False
                    print("IMPORTING TO DB")
                    try:
                        # run sql to import data into the database
                        (conn, cur) = connect_to_db()
                        cur.execute(sql_str)

                        template_dict['message'].append("Successfully imported to database")
                        template_dict['landing_page'] = '/view/dataset/%s' % uid
                    except Exception as err:
                        template_dict['error'] = "Error Importing to database: " + str(err)
                        problem = True

                    if not problem:
                        # copy uploaded files to their permanent home
                        print('Copying uploaded files')
                        json_str = request.form.get('json').encode('utf-8')
                        json_data = json.loads(json_str)
                        timestamp = json_data.get('timestamp')
                        if timestamp:
                            upload_dir = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'], timestamp)
                            uid_dir = os.path.join(current_app.root_path, app.config['DATASET_FOLDER'], 'usap-dc', uid)
                            dest_dir = os.path.join(uid_dir, timestamp)
                            try:
                                if os.path.exists(dest_dir):
                                    shutil.rmtree(dest_dir)
                                shutil.copytree(upload_dir, dest_dir)
                                # change permissions
                                os.chmod(uid_dir, 0o775)
                                for root, dirs, files in os.walk(uid_dir):
                                    for d in dirs:
                                        os.chmod(os.path.join(root, d), 0o775)
                                    for f in files:
                                        os.chmod(os.path.join(root, f), 0o664)

                            except Exception as err:
                                template_dict['error'] = "Error copying uploaded files: " + str(err)
                                problem = True

                # full curator workflow
                elif request.form.get('submit') == 'full_workflow':
                    # read in sql and submit to the database
                    sql_str = request.form.get('sql').encode('utf-8')
                    template_dict['tab'] = "sql"
                    problem = False
                    print("IMPORTING TO DB")
                    try:
                        # run sql to import data into the database
                        (conn, cur) = connect_to_db()
                        cur.execute(sql_str)

                        template_dict['message'].append("Successfully imported to database")
                        template_dict['landing_page'] = '/view/dataset/%s' % uid
                    except Exception as err:
                        template_dict['error'] = "Error Importing to database: " + str(err)
                        problem = True

                    if not problem:
                        # copy uploaded files to their permanent home
                        print('Copying uploaded files')
                        json_str = request.form.get('json').encode('utf-8')
                        json_data = json.loads(json_str)
                        timestamp = json_data.get('timestamp')
                        if timestamp:
                            upload_dir = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'], timestamp)
                            uid_dir = os.path.join(current_app.root_path, app.config['DATASET_FOLDER'], 'usap-dc', uid)
                            dest_dir = os.path.join(uid_dir, timestamp)
                            try:
                                if os.path.exists(dest_dir):
                                    shutil.rmtree(dest_dir)
                                shutil.copytree(upload_dir, dest_dir)
                                # change permissions
                                os.chmod(uid_dir, 0o775)
                                for root, dirs, files in os.walk(uid_dir):
                                    for d in dirs:
                                        os.chmod(os.path.join(root, d), 0o775)
                                    for f in files:
                                        os.chmod(os.path.join(root, f), 0o664)
                            except Exception as err:
                                template_dict['error'] = "Error copying uploaded files: " + str(err)
                                problem = True

                    if not problem:
                        # EZID DOI submission
                        print('EZID DOI submission')
                        datacite_file, status = getDataCiteXML(uid)
                        if status == 0:
                            template_dict['error'] = "Error: Unable to get DataCiteXML from database."
                            problem = True
                        else:
                            msg = submitToEZID(uid)
                            template_dict['dcxml'] = getDataCiteXMLFromFile(uid)
                            if msg.find("Error") >= 0:
                                template_dict['error'] = msg
                                problem = True
                            else:
                                template_dict['message'].append(msg)

                    if not problem:
                        # generate ISO XML file and place in watch dir for geoportal.
                        print('Generating ISO XML file')
                        msg = doISOXML(uid)
                        template_dict['isoxml'] = getISOXMLFromFile(uid)
                        print(msg)
                        if msg.find("Error") >= 0:
                            template_dict['error'] = msg
                            problem = True
                        else:
                            template_dict['message'].append(msg)

                # save updates to the readme file
                elif request.form.get('submit') == "save_readme":
                    template_dict.update(request.form.to_dict())
                    template_dict['tab'] = "readme"
                    readme_str = request.form.get('readme').encode('utf-8')
                    filename = request.form.get('readme_file')
                    try:
                        with open(filename, 'w') as out_file:
                            out_file.write(readme_str)
                        os.chmod(filename, 0o664)
                        template_dict['message'].append("Successfully updated Read Me file")
                    except:
                        template_dict['error'] = "Error updating Read Me file"

                # Standalone EZID DOI submission
                elif request.form.get('submit') == "submit_to_ezid":
                    template_dict.update(request.form.to_dict())
                    template_dict['tab'] = "dcxml"
                    xml_str = request.form.get('dcxml').encode('utf-8')
                    datacite_file = getDCXMLFileName(uid)
                    try:
                        with open(datacite_file, 'w') as out_file:
                            out_file.write(xml_str)
                        os.chmod(datacite_file, 0o664)
                        msg = submitToEZID(uid)
                        if msg.find("Error") >= 0:
                            template_dict['error'] = msg
                            problem = True
                        else:
                            template_dict['message'].append(msg)
                    except Exception as err:
                        template_dict['error'] = "Error updating DataCite XML file: " + str(err) + datacite_file

                # Standalone DataCite XML generation
                elif request.form.get('submit') == "generate_dcxml":
                    template_dict.update(request.form.to_dict())
                    template_dict['tab'] = "dcxml"
                    datacite_file, status = getDataCiteXML(uid)
                    if status == 0:
                        template_dict['error'] = "Error: Unable to get DataCiteXML from database."
                    else:
                        template_dict['dcxml'] = getDataCiteXMLFromFile(uid)

                # Standalone save ISO XML to watch dir
                elif request.form.get('submit') == "save_isoxml":
                    template_dict.update(request.form.to_dict())
                    template_dict['tab'] = "isoxml"
                    xml_str = request.form.get('isoxml').encode('utf-8')
                    isoxml_file = getISOXMLFileName(uid)
                    try:
                        with open(isoxml_file, 'w') as out_file:
                            out_file.write(xml_str)
                            template_dict['message'].append("ISO XML file saved to watch directory.")
                        os.chmod(isoxml_file, 0o664)

                    except Exception as err:
                        template_dict['error'] = "Error saving ISO XML file to watch directory: " + str(err)

                # Standalone ISO XML generation
                elif request.form.get('submit') == "generate_isoxml":
                    template_dict.update(request.form.to_dict())
                    template_dict['tab'] = "isoxml"
                    isoxml = getISOXMLFromFile(uid)
                    if isoxml.find("Error") >= 0:
                        template_dict['error'] = "Error: Unable to generate ISO XML."
                    template_dict['isoxml'] = isoxml

            else:
                # display submission json file
                try:
                    with open(submission_file) as infile:
                        data = json.load(infile)
                        submission_data = json.dumps(data, sort_keys=True, indent=4)
                        template_dict['json'] = submission_data
                except:
                    template_dict['error'] = "Can't read submission file: %s" % submission_file

    return render_template('curator.html', **template_dict)


@app.route('/curator/help', methods=['GET', 'POST'])
def curator_help():
    template_dict = {}
    template_dict['submitted_dir'] = os.path.join(current_app.root_path, app.config['SUBMITTED_FOLDER'])
    template_dict['doc_dir'] = os.path.join(current_app.root_path, "doc/{dataset_id}")
    template_dict['upload_dir'] = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'], "{upload timestamp}")
    template_dict['dataset_dir'] = os.path.join(current_app.root_path, app.config['DATASET_FOLDER'], 'usap-dc', "{dataset_id}", "{upload timestamp}")
    template_dict['watch_dir'] = os.path.join(current_app.root_path, "watch/isoxml")

    return render_template('curator_help.html', **template_dict)


def getFromDifTable(col, all_selected):
    (conn, cur) = connect_to_db()
    query = "SELECT DISTINCT %s FROM dif_test " % col
    if not all_selected:
        query += "WHERE is_usap_dc = true "
    query += "ORDER BY %s;" % col
    cur.execute(query)
    return cur.fetchall()


@app.route('/catalog_browser', methods=['GET', 'POST'])
def catalog_browser():
    all_selected = False
    template_dict = {'pi_name': '', 'title': '', 'award': '', 'dif_id': '', 'all_selected': all_selected}
    (conn, cur) = connect_to_db()

    query = "SELECT DISTINCT dif_test.*, ST_AsText(dsm.bounds_geometry) AS bounds_geometry FROM dif_test LEFT JOIN dif_spatial_map dsm ON dsm.dif_id = dif_test.dif_id WHERE dif_test.dif_id !=''"

    if request.method == 'POST':
        print(request.form)

        template_dict['pi_name'] = request.form.get('pi_name')
        template_dict['title'] = request.form.get('title')
        template_dict['summary'] = request.form.get('summary')
        template_dict['award'] = request.form.get('award')
        template_dict['dif_id'] = request.form.get('dif_id')
        all_selected = bool(int(request.form.get('all_selected')))
        template_dict['all_selected'] = all_selected

        print(bool(int(request.form.get('all_selected'))))
        if (request.form.get('pi_name') != ""):
            query += " AND dif_test.pi_name ~* '%s'" % request.form['pi_name']
        if(request.form.get('title') != ""):
            query += " AND dif_test.title ILIKE '%" + request.form['title'] + "%'"
        if(request.form.get('summary') != ""):
            query += " AND dif_test.summary ILIKE '%" + request.form['summary'] + "%'"
        if (request.form.get('award') != "" and request.form.get('award') != "Any award"):
            query += " AND dif_test.award = '%s'" % request.form['award']
        if (request.form.get('dif_id') != "" and request.form.get('dif_id') != "Any DIF ID"):
            query += " AND dif_test.dif_id = '%s'" % request.form['dif_id']

    if not all_selected:
        query += " AND dif_test.is_usap_dc = true"

    query += " ORDER BY dif_test.date_created DESC"

    query_string = cur.mogrify(query)
    print(query_string)
    cur.execute(query_string)
    rows = cur.fetchall()

    for row in rows:
        authors = row['pi_name']
        if row['co_pi'] != "":
            authors += "; %s" % row['co_pi']
        row['authors'] = authors
        if row['award'] != "":
            row['award'] = int(row['award'])
            row['award_7d'] = "%07d" % row['award']
        ds_query = "SELECT * FROM dif_data_url_map WHERE dif_id = '%s'" % row['dif_id']
        ds_query_string = cur.mogrify(ds_query)
        cur.execute(ds_query_string)
        datasets = cur.fetchall()

        # get the list of repositories
        repos = []
        for ds in datasets:
            repo = ds['repository']
            if repo not in repos:
                repos.append(repo)
        row['repositories'] = repos

        if row['dif_id'] == "NSF-ANT05-37143":
            datasets = [{'title': 'Studies of Antarctic Fungi', 'url': url_for('genBank_datasets')}]

        row['datasets'] = datasets

    template_dict['dif_records'] = rows

    if template_dict['award'] == "":
        template_dict['award'] = "Any award"

    if template_dict['dif_id'] == "":
        template_dict['dif_id'] = "Any DIF ID"

    # get list of available options for drop downs and autocomplete
    template_dict['awards'] = getFromDifTable('award', all_selected)
    template_dict['dif_ids'] = getFromDifTable('dif_id', all_selected)
    template_dict['titles'] = getFromDifTable('title', all_selected)
    template_dict['pi_names'] = getFromDifTable('pi_name', all_selected)


    return render_template('catalog_browser.html', **template_dict)


@app.route('/filter_dif_menus', methods=['GET'])
def filter_dif_menus():
    args = request.args.to_dict()
    # if reseting:
    if args == {}:
        session['search_params'] = {}

    (conn, cur) = connect_to_db()

    query_base = "SELECT award, dif_id FROM dif_test"

    if args.get('dif_id') is not None and args['dif_id'] != 'Any DIF ID' and \
       args['dif_id'] != '':
        query_string = query_base + " WHERE dif_id = '%s'" % args['dif_id']
        if args.get('all_selected') is not None and args['all_selected'] == '0':
            query_string += " AND is_usap_dc = true"
    else:
        if args.get('all_selected') is not None and args['all_selected'] == '0':
            query_string = query_base + " WHERE is_usap_dc = true"
        else:
            query_string = query_base
    cur.execute(query_string)
    dsets = cur.fetchall()
    awards = set([d['award'] for d in dsets])

    if args.get('award') is not None and args['award'] != 'Any award' and \
       args['award'] != '':
        query_string = query_base + " WHERE award = '%s'" % args['award']
        if args.get('all_selected') is not None and args['all_selected'] == '0':
            query_string += " AND is_usap_dc = true"
    else:
        if args.get('all_selected') is not None and args['all_selected'] == '0':
            query_string = query_base + " WHERE is_usap_dc = true"
        else:
            query_string = query_base
    cur.execute(query_string)
    dsets = cur.fetchall()
    dif_ids = set([d['dif_id'] for d in dsets])

    return flask.jsonify({
        'award': sorted(awards),
        'dif_id': sorted(dif_ids)
    })


@app.route('/NSF-ANT05-37143_datasets')
def genBank_datasets():
    genbank_url = "https://www.ncbi.nlm.nih.gov/nuccore/"
    (conn, cur) = connect_to_db()
    ds_query = "SELECT title FROM dif_data_url_map WHERE dif_id = 'NSF-ANT05-37143'"
    ds_query_string = cur.mogrify(ds_query)
    cur.execute(ds_query_string)
    title = cur.fetchone()
    datasets = re.split(', |\) |\n', title['title'])
    print(datasets)
    lines = []
    for ds in datasets:
        if ds.strip()[0] == "(":
            lines.append({'title': ds.replace("(", "")})
        else:
            lines.append({'title': ds, 'url': genbank_url + ds.replace(' ', '')})
    print(lines)
    template_dict = {'lines': lines}
    return render_template("NSF-ANT05-37143_datasets.html", **template_dict)


@app.route('/getfeatureinfo')
def getfeatureinfo():
    print('getfeatureinfo')
    if request.args.get('layers') != "":
        url = urllib.unquote('http://api.usap-dc.org:81/wfs?' + urllib.urlencode(request.args))
        print(url)
        print(requests.get(url).text)
        return requests.get(url).text
    return None


@app.route('/polygon')
def polygon_count():
    wkt = request.args.get('wkt')
    (conn, cur) = connect_to_db()
    query = cur.mogrify('''SELECT COUNT(*), program FROM (SELECT DISTINCT
           ds.id,
           apm.program_id as program
           FROM dataset_spatial_map dspm 
           JOIN dataset ds ON (dspm.dataset_id=ds.id)
           JOIN dataset_award_map dam ON (ds.id=dam.dataset_id)
           JOIN award_program_map apm ON (dam.award_id=apm.award_id)
           WHERE st_within(st_transform(dspm.geometry,3031),st_geomfromewkt('srid=3031;'||%s))) foo GROUP BY program''',(wkt,))
    cur.execute(query)
    return flask.jsonify(cur.fetchall())


@app.route('/titles')
def titles():
    term = request.args.get('term')
    (conn,cur) = connect_to_db()
    query_string = cur.mogrify('SELECT title FROM dataset WHERE title ILIKE %s', ('%' + term + '%',));
    cur.execute(query_string)
    rows = cur.fetchall()
    titles = []
    for r in rows:
        titles.append(r['title'])
    return flask.jsonify(titles)


@app.route('/geometries')
def geometries():
    (conn,cur) = connect_to_db()
    query = "SELECT st_asgeojson(st_transform(st_geomfromewkt('srid=4326;' || 'POLYGON((' || west || ' ' || south || ', ' || west || ' ' || north || ', ' || east || ' ' || north || ', ' || east || ' ' || south || ', ' || west || ' ' || south || '))'),3031)) as geom FROM dataset_spatial_map;"
    cur.execute(query)
    return flask.jsonify([row['geom'] for row in cur.fetchall()])


@app.route('/parameter_search')
def parameter_search():
    (conn,cur) = connect_to_db()
    expr = '%'+request.args.get('term')+'%'
    query = cur.mogrify("SELECT id FROM parameter WHERE category ILIKE %s OR topic ILIKE %s OR term ILIKE %s OR varlev1 ILIKE %s OR varlev2 ILIKE %s OR varlev3 ILIKE %s", (expr,expr,expr,expr,expr,expr))
    cur.execute(query)
    return flask.jsonify([row['id'] for row in cur.fetchall()])

# @app.route('/test_autocomplete')
# def test_autocomplete():
#     return '\n'.join([render_template('header.html'),
#                       render_template('test_autocomplete.html'),
#                       render_template('footer.html')])


@app.route('/dataset_json/<dataset_id>')
def dataset_json(dataset_id):
    return flask.jsonify(get_datasets([dataset_id]))


@app.route('/stats', methods=['GET'])
def stats():

    args = request.args.to_dict()

    template_dict = {}
    date_fmt = "%Y-%m-%d"
    if args.get('start_date'):
        start_date = datetime.strptime(args['start_date'], date_fmt)
    else:
        start_date = datetime.strptime('2011-01-01', date_fmt)
    if args.get('end_date'):
        end_date = datetime.strptime(args['end_date'], date_fmt)
    else:
        end_date = datetime.now()

    template_dict['start_date'] = start_date
    template_dict['end_date'] = end_date

    # get download information from the database
    (conn, cur) = connect_to_db()
    query = "SELECT * FROM access_logs_downloads WHERE time >= '%s' AND time <= '%s';" % (start_date, end_date)

    cur.execute(query)
    data = cur.fetchall()
    downloads = {}
    for row in data:
        time = row['time']
        month = "%s-%02d-01" % (time.year, time.month)  
        bytes = row['resource_size']
        user = row['remote_host']
        resource = row['resource_requested']
        user_file = "%s-%s" % (user, resource) 
        if downloads.get(month):
            downloads[month]['bytes'] += bytes
            downloads[month]['num_files'] += 1 
            downloads[month]['users'].add(user)
            downloads[month]['user_files'].add(user_file)
        else:
            downloads[month] = {'bytes': bytes, 'num_files': 1, 'users': {user}, 'user_files': {user_file}}

    download_numfiles_bytes = []
    download_users_downloads = []
    months_list = downloads.keys()
    months_list.sort()
    for month in months_list:
        download_numfiles_bytes.append([month, downloads[month]['num_files'], downloads[month]['bytes']])
        download_users_downloads.append([month, len(downloads[month]['users']), len(downloads[month]['user_files'])])
    template_dict['download_numfiles_bytes'] = download_numfiles_bytes
    template_dict['download_users_downloads'] = download_users_downloads

    # get submission information from the database

    query = cur.mogrify('''SELECT dsf.*, d.release_date, dt.date_created::text FROM dataset_file_info dsf 
            JOIN dataset d ON d.id = dsf.dataset_id
            LEFT JOIN dif_test dt ON d.id_orig = dt.dif_id;''') 
    cur.execute(query)
    data = cur.fetchall()
    submissions = {}
    for row in data:
        if row['date_created'] is not None:
            date = row['date_created']
        else:
            date = row['release_date']
        if date is None or date.count("-") != 2:
            # if only a year is given, make the date Dec 1st of that year
            if len(date) == 4:
                date += "-12-01"
            else:
                continue 
        # throw out any rows not in the chosen date range
        if (datetime.strptime(date, date_fmt) < start_date or
           datetime.strptime(date, date_fmt) > end_date):
            continue
        month = "%s-01" % date[:7]
        bytes = row['file_size']
        num_files = row['file_count']
        submission = row['dataset_id']
        if submissions.get(month):
            submissions[month]['bytes'] += bytes
            submissions[month]['num_files'] += num_files
            submissions[month]['submissions'].add(submission)
        else:
            submissions[month] = {'bytes': bytes, 'num_files': num_files, 'submissions': {submission}}

    submission_bytes = []
    submission_num_files = []
    submission_submissions = []
    months_list = submissions.keys()
    months_list.sort()
    for month in months_list:
        submission_bytes.append([month, submissions[month]['bytes']])
        submission_num_files.append([month, submissions[month]['num_files']])
        submission_submissions.append([month, len(submissions[month]['submissions'])])
    template_dict['submission_bytes'] = submission_bytes
    template_dict['submission_num_files'] = submission_num_files
    template_dict['submission_submissions'] = submission_submissions

    return render_template('statistics.html', **template_dict)


def initcap(s):
    parts = re.split('( |_|-|>)+',s)
    return ' '.join([p.lower().capitalize() for p in parts])


@app.errorhandler(500)
def internal_error(error):
    return redirect(url_for('not_found'))


@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for('not_found'))


app.jinja_env.globals.update(map=map)
app.jinja_env.globals.update(initcap=initcap)
app.jinja_env.globals.update(randint=randint)
app.jinja_env.globals.update(str=str)
app.jinja_env.globals.update(basename=os.path.basename)
app.jinja_env.globals.update(pathjoin=os.path.join)
app.jinja_env.globals.update(len=len)
app.jinja_env.globals.update(repr=repr)
app.jinja_env.globals.update(ceil=math.ceil)
app.jinja_env.globals.update(int=int)
app.jinja_env.globals.update(filter_awards=lambda awards: [aw for aw in awards if aw['award'] != 'XXXXXXX'])
app.jinja_env.globals.update(json_dumps=json.dumps)

if __name__ == "__main__":
    SECRET_KEY = 'development key'
    app.secret_key = SECRET_KEY
    app.run(host=app.config['SERVER_NAME'], debug=True, ssl_context=context, threaded=True)
