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
import uuid
import logging



class GecHandler(logging.Handler):
  """Log observer that writes exceptions to json files to be picked up by upload.py."""


  def __init__(self, path, project, environment, serverName, prepareException = None):
    self.__path = path
    self.__project = project
    self.__environment = environment
    self.__serverName = serverName
    self.__prepareException = prepareException
    logging.Handler.__init__(self)


  def emit(self, item):
    """Emit an error from the given event, if it was an error event."""
    result = {
      'project':self.__project,
      'environment':self.__environment,
      'serverName': self.__serverName
    }
    if item.exc_info:
      result.update(self.formatException(item))
    elif item.levelname == "ERROR":
      result.update(self.formatLogMessage(item))
    else:
      return
    output = json.dumps(result)
    filename = os.path.join(self.__path, str(uuid.uuid4()) + '.gec.json')
    if not os.path.exists(filename):
      with open(filename, 'w') as f:
        f.write(output)


  def formatLogMessage(self, item):
    """Format a log message that got triggered without an exception"""
    return {
      'type':"%s message" % item.levelname,
      'message':item.getMessage(),
      'backtrace':"%s:%d at %s" % (item.module, item.lineno, item.pathname)
    }


  def formatException(self, item):
    """Format an exception"""
    exception = {
      'type': item.exc_info[0].__module__ + '.' + item.exc_info[0].__name__,
      'message': str(item.exc_info[1]),
      'logMessage': item.message,
      'backtrace': item.exc_text
    }
    if self.__prepareException:
      return self.__prepareException(exception)
    return exception


  def stop(self):
    """Stop observing log events."""
    logging.getLogger().removeHandler(self)
