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

"""AppEngine data model for collecting exceptions."""

from google.appengine.ext import db

import config



class Queue(db.Model):
  """Model for a task in the queue."""

  payload = db.TextProperty()



class Project(db.Model):
  """Model for a project that contains errors."""



class LoggedError(db.Model):
  """Model for a logged error."""

  project = db.ReferenceProperty(Project)

  backtrace = db.TextProperty()

  type = db.StringProperty()

  hash = db.StringProperty()

  active = db.BooleanProperty()

  count = db.IntegerProperty()

  errorLevel = db.StringProperty(default = 'error')

  firstOccurrence = db.DateTimeProperty()

  lastOccurrence = db.DateTimeProperty()

  lastMessage = db.StringProperty(multiline=True)

  environments = db.StringListProperty()

  servers = db.StringListProperty()


  @classmethod
  def kind(cls):
    """Returns the datastore name for this model class."""
    return 'LoggedErrorV2_%d' % (config.get('datastoreVersion', 2))



class LoggedErrorInstance(db.Model):
  """Model for each occurrence of an error."""

  project = db.ReferenceProperty(Project)

  error = db.ReferenceProperty(LoggedError)

  environment = db.StringProperty()

  type = db.StringProperty()

  errorLevel = db.StringProperty(default = 'error')

  date = db.DateTimeProperty()

  message = db.TextProperty()

  server = db.StringProperty()

  logMessage = db.TextProperty()

  context = db.TextProperty()

  affectedUser = db.IntegerProperty()


  @classmethod
  def kind(cls):
    """Returns the datastore name for this model class."""
    return 'LoggedErrorInstanceV2_%d' % (config.get('datastoreVersion', 2))



class AggregatedStats(db.Model):
  """Stores aggregated stats."""

  date = db.DateTimeProperty()

  json = db.TextProperty()
