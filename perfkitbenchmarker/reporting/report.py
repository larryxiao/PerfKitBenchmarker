#!/usr/bin/env python

# Copyright 2017 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Reporting benchmark result, eg. into Google Sheets.

Crate a new spreadsheet before use:
1) Generate client_secret.json, refer to: https://developers.google.com/sheets/api/quickstart/python
2) python -m perfkitbenchmarker.reporting.report
Optional flag:
  --reporting_sheet_title
"""

from __future__ import print_function
import httplib2
import os
import sys

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from pprint import pprint

from perfkitbenchmarker import flags

SCOPES = 'https://www.googleapis.com/auth/drive.file'
APPLICATION_NAME = 'PerfKitBenchmarker Reporter'

FLAGS = flags.FLAGS
flags.DEFINE_boolean('reporting', False, 'Enable reporting')
flags.DEFINE_string('reporting_client_secret_file',
                    'client_secret.json',
                    'client secret file to use. Refer to '
                    'https://developers.google.com/sheets/api/quickstart/python '
                    'for generating one.')
flags.DEFINE_string('reporting_sheet_id',
                    None,
                    'The sheet id to use for reporting.')
flags.DEFINE_string('reporting_sheet_title',
                    'Cloud Spanner YCSB Benchmark',
                    'The sheet title to use for reporting.')
# TODO: parameterize individula sheet name.

# Don't report these flags
FLAG_IGNORED_PREFIX = 'reporting'

# Sample code from google sheets python quickstart
def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'perfkitbenchmarker_reporter.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        flags = None
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials

credentials = get_credentials()
http = credentials.authorize(httplib2.Http())
discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                'version=v4')
service = discovery.build('sheets', 'v4', http=http,
                          discoveryServiceUrl=discoveryUrl)

import datetime
header = ['datetime']
flags_ = {'datetime' : str(datetime.datetime.now())}
result = {}
workloads = []

def create_sheet():
    spreadsheet_body = {
        'properties' : {
            'title' : FLAGS.reporting_sheet_title
        }
    }
    request = service.spreadsheets().create(body=spreadsheet_body)
    response = request.execute()
    return response['spreadsheetId']

def get_header():
    global header
    if not FLAGS.reporting:
      return
    range_ = 'Sheet1!1:1'
    value_render_option = 'FORMATTED_VALUE'
    date_time_render_option = 'FORMATTED_STRING'
    request = service.spreadsheets().values().get(spreadsheetId=FLAGS.reporting_sheet_id, range=range_, valueRenderOption=value_render_option, dateTimeRenderOption=date_time_render_option)
    response = request.execute()
    if response.has_key('values'):
      header = response['values'][0]
    # pprint(header)

def add_flags(FLAGS):
    global header
    global workloads
    if not FLAGS.reporting:
      return
    get_header()
    for name in FLAGS:
      flag = FLAGS[name]
      if flag.present:
        if name.startswith(FLAG_IGNORED_PREFIX):
          continue
        if not flag.name in header:
          header.append(flag.name)
        flags_[flag.name] = flag.value
    workloads = flags_['ycsb_workload_files']

# TODO: add_sample, adds benchmark results in a dict
# add_sample_dimension, adds a dimesion of the results
def add_sample(key, value):
    global result
    if not FLAGS.reporting:
      return
    result[key] = value
    # update header
    if not key in header:
      header.append(key)

def flush_result():
    global result
    global workloads
    if not FLAGS.reporting:
      return
    update_header()
    if not len(result):
      return
    # split workloads
    if not len(workloads):
      flags_['ycsb_workload_files'] = 'error getting workload'
    else:
      flags_['ycsb_workload_files'] = workloads[0]
      workloads = workloads[1:]
    # build row
    row = []
    for k in header:
      if k in flags_:
        row.append(str(flags_[k]))
      elif k in result:
        row.append(str(result[k]))
      else:
        # manually added column
        row.append('')
    # write row
    range_ = 'Sheet1'
    value_input_option = 'USER_ENTERED'
    insert_data_option = 'INSERT_ROWS'
    value_range_body = {
        'values' : [
          row
        ],
    }

    request = service.spreadsheets().values().append(spreadsheetId=FLAGS.reporting_sheet_id, range=range_, valueInputOption=value_input_option, insertDataOption=insert_data_option, body=value_range_body)
    response = request.execute()
    pprint(response)
    result = {}

def update_header():
    if not FLAGS.reporting:
      return
    range_ = 'Sheet1!1:1'
    value_input_option = 'USER_ENTERED'
    value_range_body = {
        'values' : [
            header
        ],
    }

    request = service.spreadsheets().values().update(spreadsheetId=FLAGS.reporting_sheet_id, range=range_, valueInputOption=value_input_option, body=value_range_body)
    response = request.execute()
    pprint(response)

def main():
    try:
      argv = FLAGS(sys.argv)
    except flags.FlagsError as e:
      print(e)
      sys.exit(1)

    sheet_id = create_sheet()
    print("enable reporting with --reporting --reporting_sheet_id=%s" % sheet_id)

if __name__ == '__main__':
    main()
