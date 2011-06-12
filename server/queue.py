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

from common import AttrDict, getProject, parseDate
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


def aggregate(destination, count, first, last, lastMessage, backtraceText, environments, servers):
  """Aggregates in to the given destination."""
  destination.count += count

  if destination.firstOccurrence:
    destination.firstOccurrence = min(destination.firstOccurrence, first)
  else:
    destination.firstOccurrence = first

  if not destination.lastOccurrence or last > destination.lastOccurrence:
    destination.lastOccurrence = last
    destination.backtrace = backtraceText
    destination.lastMessage = lastMessage

  destination.environments = list(set(destination.environments) | set(environments))
  destination.servers = list(set(destination.servers) | set(servers))


def aggregateInstances(instances):
  """Aggregates instances in to a meta instance."""
  result = AttrDict(
    count = 0,
    firstOccurrence = None,
    lastOccurrence = None,
    lastMessage = None,
    backtrace = None,
    environments = set(),
    servers = set()
  )

  for instance in instances:
    if isinstance(instance, LoggedErrorInstance):
      count = 1
      first = instance.date
      last = instance.date
      lastMessage = instance.message[:300]
      backtraceText = instance.backtrace[:30000]
      environments = (instance.environment,)
      servers = (instance.server,)
    else:
      count = instance['count']
      first = parseDate(instance['firstOccurrence'])
      last = parseDate(instance['lastOccurrence'])
      lastMessage = instance['lastMessage']
      backtraceText = instance['backtrace']
      environments = instance['environments']
      servers = instance['servers']

    result.count += count
    aggregate(result, count, first, last, lastMessage, backtraceText, environments, servers)

  return result


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
  environment = exception.get('environment', 'Unknown')
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
  return memcache.delete(key, namespace = 'errorLocks')



class AggregationWorker(webapp.RequestHandler):
  """Worker handler for reporting a new exception."""

  def post(self):
    """Handles a new error report via POST."""
    q = taskqueue.Queue('aggregation')
    tasks = q.lease_tasks(600, 1000) # Get 1000 tasks and lease for 10 minutes
    logging.info('Leased %d tasks', len(tasks))

    byError = collections.defaultdict(list)
    instanceKeys = []
    tasksByError = collections.defaultdict(list)
    for task in tasks:
      data = json.loads(task.payload)
      errorKey = data['error']
      if 'instance' in data:
        instanceKey = data['instance']
        byError[errorKey].append(instanceKey)
        instanceKeys.append(instanceKey)
      else:
        byError[errorKey].append(data['aggregation'])
      tasksByError[errorKey].append(task)

    retries = 0
    instanceByKey = getInstanceMap(instanceKeys)
    for errorKey, instances in byError.items():
      instances = [keyOrDict if isinstance(keyOrDict, dict) else instanceByKey[keyOrDict]
                   for keyOrDict in instances]
      aggregation = aggregateInstances(instances)

      success = False
      if _lockError(errorKey):
        try:
          error = LoggedError.get(errorKey)
          aggregate(
              error, aggregation.count, aggregation.firstOccurrence,
              aggregation.lastOccurrence, aggregation.lastMessage, aggregation.backtrace,
              aggregation.environments, aggregation.servers)
          error.put()
          success = True
        except: # pylint: disable=W0702
          logging.exception('Error writing to data store for key %s.', errorKey)
        finally:
          _unlockError(errorKey)
      else:
        logging.info('Could not lock %s', errorKey)

      if not success:
        # Add a retry task.
        logging.info('Retrying aggregation for %d items for key %s', len(instances), errorKey)
        aggregation.firstOccurrence = str(aggregation.firstOccurrence)
        aggregation.lastOccurrence = str(aggregation.lastOccurrence)
        aggregation.environments = list(aggregation.environments)
        aggregation.servers = list(aggregation.servers)
        taskqueue.Queue('aggregation').add([
          taskqueue.Task(payload = json.dumps({'error': errorKey, 'aggregation': aggregation}), method='PULL')
        ])
        retries += 1

      q.delete_tasks(tasksByError[errorKey])

    if retries:
      raise Exception("Retrying %d tasks" % retries)
