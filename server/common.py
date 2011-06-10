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


def getProject(name):
  """Gets the project with the given name."""
  serialized = memcache.get('project:%s' % name)
  if serialized:
    return db.model_from_protobuf(serialized)
  else:
    return Project.get_or_insert(name)
