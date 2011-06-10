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

"""Queue system for aggregating exceptions.

DESIGN:

Step 1:

A new error instance is reported.  The instance is added to the Queue data store and the instances queue.
(this step is a remnant of an old strategy for dealing with incoming instances and will be removed in the future)

Step 2:

The "instances" queue handler is called.  It puts the LoggedErrorInstance, adds the instance key to the
"aggregation" queue, and adds a new task to the "aggregationWorker" queue.

Step 3:

The aggregationWorker queue handler is called.  It pulls from the "aggregation" queue, getting as many instances as
possible.  It groups them by the Error they are an Instance of.  New stats are computed, a lock is acquired on the
error, and a get/set is performed.  If the lock can't be acquired, the tasks are abandoned and should be picked up by
the next worker.  In this case, the worker throws an exception so that it is rerun.
"""

# pylint: disable=E0611
from google.appengine.api import memcache, taskqueue
# pylint: disable=E0611
from google.appengine.ext import webapp


import backtrace
import collections
from datetime import datetime
import hashlib
try:
  from django.utils import simplejson as json
except ImportError:
  import json
import logging

from common import getProject
from datamodel import LoggedError, LoggedErrorInstance, Queue


def getEndpoints():
  """Returns endpoints needed for queue processing."""
  return [
    ('/reportWorker', ReportWorker),
    ('/aggregationWorker', AggregationWorker)
  ]


def generateHash(exceptionType, backtraceText):
  """Generates a hash for the given exception type and backtrace."""
  hasher = hashlib.md5()
  hasher.update(exceptionType.encode('utf-8'))
  hasher.update(backtrace.normalizeBacktrace(backtraceText.encode('utf-8')))
  return hasher.hexdigest()


def getAggregatedError(project, backtraceText, errorHash):
  """Gets (and updates) the error matching the given report, or None if no matching error is found."""
  error = None

  project = getProject(project)

  q = LoggedError.all().ancestor(project).filter('hash =', errorHash).filter('active =', True)

  for possibility in q:
    if backtrace.normalizeBacktrace(possibility.backtrace) == backtrace.normalizeBacktrace(backtraceText):
      error = possibility
      break

  return error


def aggregateError(error, instance):
  """Updates the given error to include the given instance."""
  error.count += 1
  error.firstOccurrence = min(error.firstOccurrence, instance.date)
  if instance.date > error.lastOccurrence:
    error.lastOccurrence = instance.date
    error.backtrace = instance.backtrace
    error.lastMessage = instance.message[:300]

  if instance.environment not in error.environments:
    error.environments.append(instance.environment)
  if instance.server not in error.servers:
    error.servers.append(instance.server)
  return error


def queueException(serializedException):
  """Enqueues the given exception."""
  task = Queue(payload = serializedException)
  task.put()
  taskqueue.add(queue_name='instances', url='/reportWorker', params={'key': task.key()})


def queueAggregation(error, instance):
  """Enqueues a task to aggregate the given instance in to the given error."""
  payload = {'error': str(error.key()), 'instance': str(instance.key())}
  taskqueue.Queue('aggregation').add([
    taskqueue.Task(payload = json.dumps(payload), method='PULL')
  ])
  taskqueue.add(queue_name='aggregationWorker',
                url='/aggregationWorker')


def _putInstance(exception):
  """Put an exception in the data store."""
  backtraceText = exception['backtrace']
  environment = exception['environment']
  message = exception['message'] or ''
  project = exception['project']
  server = exception['serverName']
  timestamp = datetime.fromtimestamp(exception['timestamp'])
  exceptionType = exception['type']
  logMessage = exception.get('logMessage')
  context = exception.get('context')
  errorLevel = exception.get('errorLevel')

  errorHash = generateHash(exceptionType, backtraceText)

  error = getAggregatedError(project, backtraceText, errorHash)

  exceptionType = exceptionType.replace('\n', ' ')
  if len(exceptionType) > 500:
    exceptionType = exceptionType[:500]
  exceptionType = exceptionType.replace('\n', ' ')

  needsAggregation = True
  if not error:
    error = LoggedError(parent = getProject(project))
    error.backtrace = backtraceText
    error.type = exceptionType
    error.hash = errorHash
    error.active = True
    error.errorLevel = errorLevel
    error.count = 1
    error.firstOccurrence = timestamp
    error.lastOccurrence = timestamp
    error.lastMessage = message[:300]
    error.environments = [str(environment)]
    error.servers = [server]
    error.put()
    needsAggregation = False

  instance = LoggedErrorInstance(parent = error)
  instance.environment = environment
  instance.type = exceptionType
  instance.errorLevel = errorLevel
  instance.date = timestamp
  instance.message = message
  instance.server = server
  instance.logMessage = logMessage
  instance.backtrace = backtraceText
  if context:
    instance.context = json.dumps(context)
    if 'userId' in context:
      instance.affectedUser = int(context['userId'])
  instance.put()

  if needsAggregation:
    queueAggregation(error, instance)



class ReportWorker(webapp.RequestHandler):
  """Worker handler for reporting a new exception."""

  def post(self):
    """Handles a new error report via POST."""
    task = Queue.get(self.request.get('key'))
    if not task:
      return

    exception = json.loads(task.payload)
    _putInstance(exception)
    task.delete()



def getInstanceMap(instanceKeys):
  """Gets a map from key to instance for the given keys."""
  instances = LoggedErrorInstance.get(instanceKeys)
  return dict(zip(instanceKeys, instances))


def _lockError(key):
  """Locks the given error."""
  # Since it's memcache, this technically can fail, but the failure case is just slightly inaccurate data.
  return memcache.add(key, True, time = 600, namespace = 'errorLocks')


def _unlockError(key):
  """Locks the given error."""
  return memcache.delete(key, True, namespace = 'errorLocks')



class AggregationWorker(webapp.RequestHandler):
  """Worker handler for reporting a new exception."""

  def post(self):
    """Handles a new error report via POST."""
    q = taskqueue.Queue('aggregation')
    tasks = q.lease_tasks(600, 1000) # Get 1000 tasks and lease for 10 minutes

    byError = collections.defaultdict(list)
    instanceKeys = []
    tasksByError = collections.defaultdict(list)
    for task in tasks:
      data = json.loads(task.payload)
      instanceKey = data['instance']
      byError[data['error']].append(instanceKey)
      tasksByError[data['error']].append(task)
      instanceKeys.append(instanceKey)

    errors = []
    retryTasks = []
    instanceByKey = getInstanceMap(instanceKeys)
    for errorKey, instanceKeys in byError.items():
      if not _lockError(errorKey):
        errors.append(errorKey)
        retryTasks.extend(tasksByError[errorKey])
        break

      try:
        for instanceKey in instanceKeys:
          error = LoggedError.get(errorKey)
          aggregateError(error, instanceByKey[instanceKey])
          error.put()
        q.delete_tasks(tasksByError[errorKey])
      finally:
        _unlockError(errorKey)

    if errors:
      q.delete_tasks(retryTasks)
      logging.info("Retrying %d tasks", len(retryTasks))
      for task in retryTasks:
        taskqueue.Queue('aggregation').add([
          taskqueue.Task(payload = task.payload, method='PULL')
        ])
      raise Exception('Locks failed when trying to lock errors %s' % ', '.join(errors))
