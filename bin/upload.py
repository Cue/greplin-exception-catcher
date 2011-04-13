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
import os.path
import shutil
import stat
import sys
import urllib2


def handleError(e, message, filename):
  """Handles an error by printing it and marking the file as available but with an additional strike."""
  print message % filename
  print e
  shutil.move(filename + '.processing', os.path.join(os.path.dirname(filename), '_' + os.path.basename(filename)))


def main():
  """Runs the gec sender."""
  server = sys.argv[1]
  secretKey = sys.argv[2]
  path = sys.argv[3]

  for filename in os.listdir(path):
    filename = os.path.join(path, filename)
    if filename.endswith('.gec.json') and not '_____' in filename:
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

        request = urllib2.Request('%s/report?key=%s' % (server, secretKey),
                                  json.dumps(result),
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
        os.remove(processingFilename)


if __name__ == '__main__':
  main()
