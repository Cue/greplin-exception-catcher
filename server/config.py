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

"""Configuration utilities."""

try:
  from django.utils import simplejson as json
except ImportError:
  import json


def _loadConfig():
  """Loads application configuration."""
  f = open('config.json')
  try:
    return json.loads(f.read())
  finally:
    f.close()


CONFIG = _loadConfig()


def get(key, default = None):
  """Gets a configuration value."""
  return CONFIG.get(key, default)
