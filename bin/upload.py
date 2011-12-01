#!/usr/bin/env python
# Copyright 2011 The greplin-exception-catcher Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Cron for sending exception logs to greplin-exception-catcher.

Usage: upload.py http://server.com secretKey exceptionDirectory
"""

import json
import os
import time
import os.path
import sys
import urllib2, httplib
import fcntl
import signal
import traceback

# max field size
MAX_FIELD_SIZE = 1024 * 10

# HTTP request timeout
HTTP_TIMEOUT = 5

# Maximum time we should run for
MAX_RUN_TIME = 40

# Settings dict will be used to pass "server" and "secretKey" around.
SETTINGS = {}

# Documents processed and total. These are global stats.
DOCUMENTS_PROCESSED, DOCUMENTS_TOTAL = 0, '[unknown]'


def trimDict(obj):
  """Trim string elements in a dictionnary to MAX_FIELD_SIZE"""
  for k, v in obj.items():
    if isinstance(v, basestring) and len(v) > MAX_FIELD_SIZE:
      obj[k] = v[:MAX_FIELD_SIZE] + '(...)'
    elif isinstance(v, dict):
      trimDict(v)


def sendException(jsonData, filename):
  """Send an exception to the GEC server
     Returns True if sending succeeded"""

  request = urllib2.Request('%s/report?key=%s' % (SETTINGS["server"], SETTINGS["secretKey"]),
                            json.dumps(jsonData),
                            {'Content-Type': 'application/json'})
  try:
    response = urllib2.urlopen(request, timeout=HTTP_TIMEOUT)

  except urllib2.HTTPError, e:
    print >> sys.stderr, 'Error from server while uploading %s' % filename
    print >> sys.stderr, e.read()
    return False

  except urllib2.URLError, e:    
    if e.reason not in ('timed out', 'The read operation timed out'):
      print >> sys.stderr, 'Error while uploading %s' % filename
      print >> sys.stderr, e
      print >> sys.stderr, 'Reason: %s' % e.reason
    return False

  except httplib.BadStatusLine, e:
    print >> sys.stderr, 'Bad status line from server while uploading %s' % filename
    print >> sys.stderr, e
    print >> sys.stderr, 'Status line: %r' % e.line
    return False

  status = response.getcode()

  if status != 200:
    raise Exception('Unexpected status code: %d' % status)

  global DOCUMENTS_PROCESSED            # pylint: disable=W0603
  DOCUMENTS_PROCESSED += 1
  return True


def processFiles(files):
  """Send each exception file in files to GEC"""
  endTime = time.time() + MAX_RUN_TIME  
  
  for filename in files:
    if time.time() > endTime:
      return
    if not os.path.exists(filename):
      continue
    try:
      if processFile(filename):
        os.unlink(filename)
    except Exception, e: #pylint:disable=W0703
      print >> sys.stderr, e
      os.unlink(filename)


def processFile(filename):
  """Process and upload a file.
  Return True if the file has been processed as completely as it will ever be and can be deleted"""

  with open(filename, 'r+') as f:
    try:
      # make sure we're alone on that file
      fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
      return False

    try:
      result = json.load(f)
      st = os.stat(filename)
      result['timestamp'] = st.st_ctime
      trimDict(result)
      return sendException(result, filename)
    except ValueError, ex:
      print >> sys.stderr, "Could not read %s:" % filename
      print >> sys.stderr, '\n"""'
      f.seek(0)
      print >> sys.stderr, f.read()
      print >> sys.stderr, '"""\n'
      print >> sys.stderr, str(ex)
      return True # so this bogus file gets deleted
    finally:
      fcntl.lockf(f, fcntl.LOCK_UN)


        
def alarmHandler(_, frame):
  """SIGALRM handler"""
  print >> sys.stderr, "Maximum run time reached after processing %s of %s exceptions. Exiting." \
        % (DOCUMENTS_PROCESSED, DOCUMENTS_TOTAL)
  traceback.print_stack(frame, file=sys.stderr)
  sys.exit(0)


def main():
  """Runs the gec sender."""

  if len(sys.argv) not in (3, 4):
    print """USAGE: upload.py SERVER SECRET_KEY PATH [LOCKNAME]

LOCKNAME defaults to 'upload-lock'"""
    sys.exit(1)


  SETTINGS["server"] = sys.argv[1]
  SETTINGS["secretKey"] = sys.argv[2]
  path = sys.argv[3]

  signal.signal(signal.SIGALRM, alarmHandler)
  signal.alarm(int(MAX_RUN_TIME * 1.1))

  files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".gec.json")]

  global DOCUMENTS_TOTAL                # pylint: disable=W0603
  DOCUMENTS_TOTAL = len(files)
  processFiles(files)


if __name__ == '__main__':
  main()
