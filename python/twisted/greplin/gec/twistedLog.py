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

"""Classes for logging exceptions to files suitable for sending to gec."""

import json
import os.path
import traceback
import uuid
import random

from twisted.python import log, util

try:
  from greplin.defer import context
except ImportError:
  # pylint: disable=C0103
  context = None



class GecLogObserver(object):
  """Log observer that writes exceptions to json files to be picked up by upload.py."""

  BUILT_IN_KEYS = frozenset(['failure', 'message', 'time', 'why', 'isError', 'system'])


  def __init__(self, path, project, environment, serverName):
    self.__path = path
    self.__project = project
    self.__environment = environment
    self.__serverName = serverName


  def __formatFailure(self, failure, logMessage, extras):
    """Generates a dict from the given Failure object."""

    parts = ['Traceback (most recent call last):']
    if not failure.frames:
      parts += traceback.format_stack()
    else:
      for functionName, filename, lineNumber, _, _ in failure.frames:
        parts.append('File "%s", line %s, in %s' % (filename, lineNumber, functionName))
    backtrace = '\n'.join(parts)

    result = {
      'project': self.__project,
      'type': failure.type.__module__ + '.' + failure.type.__name__,
      'message': str(failure.value),
      'environment': self.__environment,
      'serverName': self.__serverName,
      'logMessage': logMessage,
      'backtrace': backtrace,
      'loggedFrom': '\n'.join(traceback.format_stack())
    }

    if extras and 'level' in extras:
      result['errorLevel'] = extras['level']
      del extras['level']

    if context and context.all():
      result['context'] = context.all()
      if extras:
        result['context'] = result['context'].copy()
        result['context'].update(extras)
    elif extras:
      result['context'] = extras

    return result


  def emit(self, eventDict):
    """Emit an error from the given event, if it was an error event."""
    if 'failure' in eventDict:
      extras = {}
      for key, value in eventDict.items():
        if key not in self.BUILT_IN_KEYS:
          extras[key] = value

      output = json.dumps(self.__formatFailure(eventDict['failure'], eventDict.get('why'), extras))
      self.write(output)


  def write(self, output):
    """Write a GEC error report, making sure we do not overwrite an existing one
    """
    while True:
      filename = os.path.join(self.__path, str(uuid.uuid4()) + '.gec.json')
      if not os.path.exists(filename):
        with open(filename, 'w') as f:
          util.untilConcludes(f.write, output)
          util.untilConcludes(f.flush)
        break


  def start(self):
    """Start observing log events."""
    log.addObserver(self.emit)


  def stop(self):
    """Stop observing log events."""
    log.removeObserver(self.emit)



class GentleGecLogObserver(GecLogObserver):
  """A GEC Handler that conserves disk space by overwriting errors."""

  MAX_BASENAME = 10
  MAX_ERRORS = 10000


  def __init__(self, path, project, environment, serverName):
    GecLogObserver.__init__(self, path, project, environment, serverName)
    self.baseName = random.randint(0, GentleGecLogObserver.MAX_BASENAME)
    self.errorId = random.randint(0, GentleGecLogObserver.MAX_ERRORS)


  def write(self, output):
    """Write a gec error report, possibly overwriting a previous one."""
    self.errorId = (self.errorId + 1) % GentleGecLogObserver.MAX_ERRORS
    filename = os.path.join(self._GecHandler__path, '%d-%d.gec.json' % (self.baseName, self.errorId))
    with open(filename, 'w') as f:
      util.untilConcludes(f.write, output)
      util.untilConcludes(f.flush)

