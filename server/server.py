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

"""AppEngine server for collecting exceptions."""

# pylint: disable=E0611
from google.appengine.dist import use_library
use_library('django', '1.2')

# pylint: disable=E0611
from google.appengine.api import memcache, taskqueue, users
# pylint: disable=E0611
from google.appengine.ext import db, webapp
# pylint: disable=E0611
from google.appengine.ext.webapp import template
# pylint: disable=E0611
from google.appengine.ext.webapp.util import run_wsgi_app

import backtrace
import config

from datetime import datetime, timedelta
import hashlib

try:
  from django.utils import simplejson as json
except ImportError:
  import json
import logging
import os
import random
import sys
import time
import traceback

from datamodel import  Queue, Project, LoggedError, LoggedErrorInstance, AggregatedStats


####### Parse the configuration. #######

NAME = config.get('name')

SECRET_KEY = config.get('secretKey')

REQUIRE_AUTH = config.get('requireAuth', True)



####### Utility methods. #######

def getTemplatePath(name):
  """Gets a path to the named template."""
  return os.path.join(os.path.dirname(__file__), 'templates', name)


def generateHash(exceptionType, backtraceText):
  """Generates a hash for the given exception type and backtrace."""
  hasher = hashlib.md5()
  hasher.update(exceptionType.encode('utf-8'))
  hasher.update(backtrace.normalizeBacktrace(backtraceText.encode('utf-8')))
  return hasher.hexdigest()


INSTANCE_FILTERS = ('environment', 'server', 'affectedUser')

INTEGER_FILTERS = ('affectedUser',)


def getFilters(request):
  """Gets the filters applied to the given request."""
  filters = {}
  for key, value in request.params.items():
    if key in INSTANCE_FILTERS or key in ('project', 'errorLevel'):
      filters[key] = value
  return filters


def filterData(dataSet, key, value):
  """Filters a data set."""
  if key in INTEGER_FILTERS:
    return dataSet.filter(key + ' =', int(value))
  else:
    return dataSet.filter(key + ' =', value)


def getErrors(filters, limit, offset):
  """Gets a list of errors, filtered by the given filters."""
  for key in filters:
    if key in INSTANCE_FILTERS:
      return None, getInstances(filters, limit=limit, offset=offset)

  errors = LoggedError.all().filter('active =', True)
  for key, value in filters.items():
    if key == 'project':
      errors = errors.ancestor(getProject(value))
    else:
      errors = errors.filter(key, value)
  errors = errors.order('-lastOccurrence')

  return errors.fetch(limit, offset), None


def getInstances(filters, parent = None, limit = None, offset = None):
  """Gets a list of instances of the given parent error, filtered by the given filters."""

  query = LoggedErrorInstance.all()
  if parent:
    query = query.ancestor(parent)

  if filters:
    for key, value in filters.items():
      if key in INSTANCE_FILTERS:
        query = filterData(query, key, value)
      elif key == 'project':
        query = query.ancestor(getProject(value))

  return query.order('-date').fetch(limit or 51, offset or 0)


def getProject(name):
  """Gets the project with the given name."""
  serialized = memcache.get('project:%s' % name)
  if serialized:
    return db.model_from_protobuf(serialized)
  else:
    return Project.get_or_insert(name)


def getAggregatedError(project, environment, server, backtraceText, errorHash, message, timestamp):
  """Gets (and updates) the error matching the given report, or None if no matching error is found."""
  error = None

  project = getProject(project)

  key = '%s|%s' % (project, errorHash)
  serialized = memcache.get(key)
  if serialized:
    error = db.model_from_protobuf(serialized)
  else:
    q = LoggedError.all().ancestor(project).filter('hash =', errorHash).filter('active =', True)

    for possibility in q:
      if backtrace.normalizeBacktrace(possibility.backtrace) == backtrace.normalizeBacktrace(backtraceText):
        error = possibility
        break

  if error:
    error.count += 1
    error.firstOccurrence = min(error.firstOccurrence, timestamp)
    if timestamp > error.lastOccurrence:
      error.lastOccurrence = timestamp
      error.backtrace = backtraceText
      error.lastMessage = message[:300]

    if environment not in error.environments:
      error.environments.append(environment)
    if server not in error.servers:
      error.servers.append(server)
    error.put()
    memcache.set(key, db.model_to_protobuf(error))
    return error


def putException(exception):
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

  error = getAggregatedError(project, environment, server, backtraceText, errorHash, message, timestamp)

  exceptionType = exceptionType.replace('\n', ' ')
  if len(exceptionType) > 500:
    exceptionType = exceptionType[:500]
  exceptionType = exceptionType.replace('\n', ' ')

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

  instance = LoggedErrorInstance(parent = error)
  instance.environment = environment
  instance.type = exceptionType
  instance.errorLevel = errorLevel
  instance.date = timestamp
  instance.message = message
  instance.server = server
  instance.logMessage = logMessage
  if context:
    instance.context = json.dumps(context)
    if 'userId' in context:
      instance.affectedUser = int(context['userId'])

  instance.put()


####### Pages #######

class AuthPage(webapp.RequestHandler):
  """Base class for pages that require authentication."""

  def __getUser(self):
    """Gets a user."""
    return users.get_current_user()


  def get(self, *args):
    """Handles a get, ensuring the user is authenticated."""
    user = self.__getUser()
    if user or not REQUIRE_AUTH:
      self.doAuthenticatedGet(user, *args)
    else:
      self.redirect(users.create_login_url(self.request.uri))


  def doAuthenticatedGet(self, _, *__):
    """Performs a get with an authenticated user."""
    self.error(500)


  def post(self, *args):
    """Handles a post, ensuring the user is authenticated."""
    user = self.__getUser()
    if user or not REQUIRE_AUTH:
      self.doAuthenticatedPost(user, *args)
    else:
      self.redirect(users.create_login_url(self.request.uri))


  def doAuthenticatedPost(self, _, *__):
    """Performs a post with an authenticated user."""
    self.error(500)



class ReportPage(webapp.RequestHandler):
  """Page handler for reporting a new exception."""

  def post(self):
    """Handles a new error report via POST."""
    key = self.request.get('key')

    if key != SECRET_KEY:
      self.error(403)
      return

    # Add the task to the instances queue.
    task = Queue(payload = self.request.body)
    task.put()
    taskqueue.add(queue_name='instances', url='/reportWorker', params={'key': task.key()})



class StatPage(webapp.RequestHandler):
  """Page handler for collecting error instance stats."""

  def get(self):
    """Handles a new error report via POST."""
    key = self.request.get('key')

    if key != SECRET_KEY:
      self.error(403)
      return

    counts = []
    project = self.request.get('project')
    if project:
      project = getProject(project)
      if not project:
        self.response.out.write(' '.join(['0' for _ in counts]))
    for minutes in self.request.get('minutes').split():
      query = LoggedErrorInstance.all()
      if project:
        query = query.ancestor(project)
      counts.append(query.filter('date >=', datetime.now() - timedelta(minutes = int(minutes))).count())

    self.response.out.write(' '.join((str(count) for count in counts)))



class AggregateViewPage(webapp.RequestHandler):
  """Page handler for collecting error instance stats."""

  def get(self, viewLength):
    """Handles a new error report via POST."""
    if viewLength != 'day':
      # TODO(robbyw): For viewLength == week or viewLength == month, aggregate the aggregates.
      viewLength = 'day'

    data = AggregatedStats.all().order('-date').get()
    data = json.loads(data.json)[:25]

    for _, row in data:
      logging.info(row)
      row['servers'] = sorted(row['servers'].items(), key = lambda x: x[1], reverse=True)
      row['environments'] = sorted(row['environments'].items(), key = lambda x: x[1], reverse=True)

    keys, values = zip(*data)
    errors = LoggedError.get([db.Key(key) for key in keys])

    context = {
      'title': 'Top 25 exceptions over the last %s' % viewLength,
      'errors': zip(errors, values),
      'total': len(data)
    }
    self.response.out.write(template.render(getTemplatePath('aggregation.html'), context))



class ReportWorker(webapp.RequestHandler):
  """Worker handler for reporting a new exception."""

  def post(self):
    """Handles a new error report via POST."""
    task = Queue.get(self.request.get('key'))
    if not task:
      return

    exception = json.loads(task.payload)
    putException(exception)
    task.delete()



class ListPage(AuthPage):
  """Page displaying a list of exceptions."""

  def doAuthenticatedGet(self, user):
    self.response.headers['Content-Type'] = 'text/html'

    filters = getFilters(self.request)

    page = int(self.request.get('page', 0))
    errors, instances = getErrors(filters, limit = 51, offset = page * 50)

    if errors is not None:
      hasMore = len(errors) == 51
      errors = errors[:50]
    else:
      hasMore = len(instances) == 51
      instances = instances[:50]

    context = {
      'title': NAME,
      'extraScripts': ['list'],
      'user': user,
      'filters': filters.items(),
      'errors': errors,
      'instances': instances,
      'hasMore': hasMore,
      'nextPage': page + 1
    }
    self.response.out.write(template.render(getTemplatePath('list.html'), context))



class ViewPage(AuthPage):
  """Page displaying a single exception."""

  def doAuthenticatedGet(self, user, *args):
    key, = args
    self.response.headers['Content-Type'] = 'text/html'
    error = LoggedError.get(key)
    filters = getFilters(self.request)
    context = {
      'title': '%s - %s' % (error.lastMessage, NAME),
      'extraScripts': ['view'],
      'user': user,
      'error': error,
      'filters': filters.items(),
      'instances': getInstances(filters, parent=error)[:100]
    }
    self.response.out.write(template.render(getTemplatePath('view.html'), context))



class ResolvePage(AuthPage):
  """Page that resolves an exception."""

  def doAuthenticatedGet(self, _, *args):
    key, = args
    self.response.headers['Content-Type'] = 'text/plain'
    error = LoggedError.get(key)
    error.active = False
    error.put()

    key = '%s|%s' % (error.parent_key().name(), error.hash)
    memcache.delete(key)

    self.response.out.write('ok')



class ClearDatabasePage(AuthPage):
  """Page for clearing the database."""

  def doAuthenticatedGet(self, _):
    if users.is_current_user_admin():
      for error in LoggedError.all():
        error.delete()
      for instance in LoggedErrorInstance.all():
        instance.delete()
      self.response.out.write('Done')
    else:
      self.redirect(users.create_login_url(self.request.uri))



class ErrorPage(webapp.RequestHandler):
  """Page that generates demonstration errors."""

  def get(self):
    """Handles page get for the error page."""
    for _ in range(10):
      error = random.choice(range(4))
      errorLevel = 'error'
      project = 'frontend'
      try:
        if error == 0:
          project = 'backend'
          x = 10 / 0
        elif error == 1:
          errorLevel = 'warning'
          json.loads('{"abc", [1, 2')
        elif error == 2:
          x = {}
          x = x['y']
        elif error == 3:
          x = {}
          x = x['z']

      except (KeyError, ZeroDivisionError, ValueError):
        excInfo = sys.exc_info()
        stack = traceback.format_exc()
        env = random.choice(['dev', 'prod'])
        exception = {
          'timestamp': time.time(),
          'project': project,
          'serverName':'%s %s %d' % (env, project, random.choice(range(3))),
          'type': excInfo[0].__module__ + '.' + excInfo[0].__name__,
          'environment': env,
          'errorLevel': errorLevel,
          'message': str(excInfo[1]),
          'logMessage': 'Log message goes here',
          'backtrace': stack,
          'context':{'userId':random.choice(range(20))}
        }
        putException(exception)

    self.response.out.write('Done!')


####### Application. #######

def main():
  """Runs the server."""
  endpoints = [
    ('/', ListPage),

    ('/clear', ClearDatabasePage),

    ('/report', ReportPage),
    ('/reportWorker', ReportWorker),

    ('/view/(.*)', ViewPage),
    ('/resolve/(.*)', ResolvePage),

    ('/stats', StatPage),
    ('/review/(.*)', AggregateViewPage),
  ]
  if config.get('demo'):
    endpoints.append(('/error', ErrorPage))
  application = webapp.WSGIApplication(endpoints, debug=True)

  run_wsgi_app(application)


if __name__ == "__main__":
  main()
