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

"""Common utility functions."""

# pylint: disable=E0611
from google.appengine.api import memcache
# pylint: disable=E0611
from google.appengine.ext import db

from datamodel import Project

import datetime
import os.path


def getProject(name):
  """Gets the project with the given name."""
  serialized = memcache.get(name, namespace = 'projects')
  if serialized:
    return db.model_from_protobuf(serialized)
  else:
    result = Project.get_or_insert(name)
    memcache.set(name, db.model_to_protobuf(result), namespace = 'projects')
    return result


def parseDate(string):
  """Parses an ISO format date string."""
  return datetime.datetime.strptime(string.split('.')[0], '%Y-%m-%d %H:%M:%S')


def getTemplatePath(name):
  """Gets a path to the named template."""
  return os.path.join(os.path.dirname(__file__), 'templates', name)



class AttrDict(dict):
  """A dict that is accessible as attributes."""

  def __getattr__(self, name):
    return self[name]


  def __setattr__(self, name, value):
    self[name] = value
