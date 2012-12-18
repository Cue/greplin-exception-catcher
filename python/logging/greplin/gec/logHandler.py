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
import os
import os.path
import uuid
import logging
import time
import random



class GecHandler(logging.Handler):
  """Log observer that writes exceptions to json files to be picked up by upload.py."""


  def __init__(self, path, project, environment, serverName, prepareMessage=None):
    self.__path = path
    self.__project = project
    self.__environment = environment
    self.__serverName = serverName
    self.__prepareMessage = prepareMessage
    logging.Handler.__init__(self)


  def emit(self, item):
    """Emit an error from the given event, if it was an error event."""
    if item.exc_info:
      formatted = self.formatException(item)
    else:
      formatted = self.formatLogMessage(item)
    result = {
      'project': self.__project,
      'environment': self.__environment,
      'serverName': self.__serverName,
      'errorLevel': item.levelname,
    }
    result.update(formatted)
    self.write(json.dumps(result))


  def write(self, output):
    """Write an exception to disk, possibly overwriting a previous one"""
    filename = os.path.join(self.__path, str(uuid.uuid4()) + '.gec.json')
    if not os.path.exists(filename):
      with open(filename, 'w') as f:
        f.write(output)


  def formatLogMessage(self, item):
    """Format a log message that got triggered without an exception"""
    try:
      itemMessage = item.getMessage()
    except TypeError:
      itemMessage = 'Error formatting message'

    log = {
      'type': "%s message" % item.levelname,
      'message': itemMessage,
      'backtrace': "%s:%d at %s" % (item.module, item.lineno, item.pathname)
    }
    if self.__prepareMessage:
      return self.__prepareMessage(log)
    return log


  def formatException(self, item):
    """Format an exception"""
    exception = {
      'type': item.exc_info[0].__module__ + '.' + item.exc_info[0].__name__,
      'message': str(item.exc_info[1]),
      'logMessage': getattr(item, 'message', None) or getattr(item, 'msg', None),
      'backtrace': item.exc_text,
      'loggedFrom': "%s:%d at %s" % (item.module, item.lineno, item.pathname)
    }
    if self.__prepareMessage:
      return self.__prepareMessage(exception)
    return exception


  def stop(self):
    """Stop observing log events."""
    logging.getLogger().removeHandler(self)



class GentleGecHandler(GecHandler):
  """A GEC Handler that conserves disk space by overwriting errors
  """

  MAX_BASENAME = 10
  MAX_ERRORS = 10000


  def __init__(self, path, project, environment, serverName, prepareException=None):
    GecHandler.__init__(self, path, project, environment, serverName, prepareException)
    self.baseName = random.randint(0, GentleGecHandler.MAX_BASENAME)
    self.errorId = random.randint(0, GentleGecHandler.MAX_ERRORS)


  def write(self, output):
    self.errorId = (self.errorId + 1) % GentleGecHandler.MAX_ERRORS
    filename = os.path.join(self._GecHandler__path, '%d-%d.gec.json' % (self.baseName, self.errorId))
    with open(filename, 'w') as f:
      f.write(output)



class SpaceAwareGecHandler(GecHandler):
  """A gec log handler that will stop logging when free disk space / inodes become too low
  """

  SPACE_CHECK_COUNTER_MAX = 128
  LIMITED_LOGGING_PC = 0.3
  NO_LOGGING_PC = 0.1


  def __init__(self, path, project, environment, serverName, prepareException=None):
    GecHandler.__init__(self, path, project, environment, serverName, prepareException)
    self.spaceCheckCounter = 0
    self.lastStatus = True


  def logDiskSpaceError(self):
    """Log an error message complaining about low disk space (instead of the original message)
    """
    noSpaceLeft = {'created': time.time(),
                   'process': os.getpid(),
                   'module': 'greplin.gec.logging.logHandler',
                   'levelno': 40,
                   'exc_text': None,
                   'lineno': 113,
                   'msg': 'Not enough free blocks/inodes on this disk',
                   'exc_info': None,
                   'funcName': 'checkSpace',
                   'levelname': 'ERROR'}
    GecHandler.emit(self, logging.makeLogRecord(noSpaceLeft))


  def doCheckSpace(self):
    """Check blocks/inodes and log an error if we're too low on either
    """
    vfsStat = os.statvfs(self._GecHandler__path)
    blocksLeft = float(vfsStat.f_bavail) / vfsStat.f_blocks
    inodesLeft = float(vfsStat.f_favail) / vfsStat.f_files
    if blocksLeft < self.LIMITED_LOGGING_PC or inodesLeft < self.LIMITED_LOGGING_PC:
      self.lastStatus = False
      if blocksLeft > self.NO_LOGGING_PC or inodesLeft > self.NO_LOGGING_PC:
        self.logDiskSpaceError()
    else:
      self.lastStatus = True


  def checkSpace(self):
    """Runs the actual disk space check only on every SPACE_CHECK_COUNTER_MAX calls
    """
    self.spaceCheckCounter -= 1
    if self.spaceCheckCounter < 0:
      self.spaceCheckCounter = GentleGecHandler.SPACE_CHECK_COUNTER_MAX
      self.doCheckSpace()
    return self.lastStatus


  def emit(self, item):
    """Log a message if we have enough disk resources.
    """
    if self.checkSpace():
      GecHandler.emit(self, item)


