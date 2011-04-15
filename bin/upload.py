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
import shutil
import stat
import sys
import urllib2

FILES_TO_KEEP = 2000
SETTINGS = {}


def handleError(e, message, filename):
  """Handles an error by printing it and marking the file as available but with an additional strike."""
  print message % filename
  print e
  shutil.move(filename + '.processing', os.path.join(os.path.dirname(filename), '_' + os.path.basename(filename)))


def reportTooManyExceptions(deleted, example):
  """Report a special message to the GEC server if we see too many exception"""
  newErr = {}
  newErr["project"] = "GEC"
  newErr["environment"] = example["environment"]
  newErr["serverName"] = example["serverName"]
  newErr["message"] = "Too many exceptions - GEC deleted %d" % deleted
  newErr["timestamp"] = int(time.time())
  sendException(newErr, "NoFilename")
  

def sendException(jsonData, filename):
  """Send an exception to the GEC server"""
  request = urllib2.Request('%s/report?key=%s' % (SETTINGS["server"], SETTINGS["secretKey"]),
                            json.dumps(jsonData),
                            {'Content-Type': 'application/json'})
  try:
    response = urllib2.urlopen(request)
  except urllib2.HTTPError, e:
    handleError(e, 'Error from server while uploading %s', filename)
    print e.read()
    return
  except urllib2.URLError, e:
    handleError(e, 'Error while uploading %s', filename)
    return
  status = response.getcode()
  if status != 200:
    raise Exception('Unexpected status code: %d' % status)

  
def main():
  """Runs the gec sender."""
  SETTINGS["server"] = sys.argv[1]
  SETTINGS["secretKey"] = sys.argv[2]
  path = sys.argv[3]
  
  files = [os.path.join(path, f) for f in os.listdir(path)
           if f.endswith(".gec.json") and not '_____' in f]

  # only keep the newest FILES_TO_KEEP entries
  outstanding = len(files)
  if outstanding > FILES_TO_KEEP:
    deleted = outstanding-FILES_TO_KEEP
    files = sorted(files, key=os.path.getctime)
    with open(files[0]) as f:
      reportTooManyExceptions(deleted, json.load(f))
    [os.remove(f) for f in files[0:deleted] if os.path.exists(f)]
    files = files[deleted:]


  for filename in files:
    if os.path.exists(filename):
      processingFilename = filename + '.processing'
      try:
        shutil.move(filename, processingFilename)
      except IOError:
        # Usually this happens when another process processes the same file.
        continue
      try:
        with open(processingFilename) as f:
          result = json.load(f)
      except ValueError:
        with open(processingFilename) as f:
          print >> sys.stderr, "Could not read %s:" % filename
          print >> sys.stderr, f.read()
          print >> sys.stderr, '\n------------------\n'
        os.remove(processingFilename)
        continue
      result['timestamp'] = os.stat(processingFilename)[stat.ST_CTIME]
      sendException(result, filename)
      os.remove(processingFilename)


if __name__ == '__main__':
  main()
