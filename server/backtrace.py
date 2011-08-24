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

"""Backtrace normalization."""

import re


REMOVE_JAVA_MESSAGE = re.compile(r'(Caused by: [^:]+:).*$', re.MULTILINE)

REMOVE_PYTHON_MESSAGE = re.compile(r'^([a-zA-Z0-9_]+: ).*$', re.MULTILINE)

REMOVE_OBJECTIVE_C_ADDRESS = re.compile(r'0x[0-9a-f]{8} ')


def normalizeBacktrace(backtrace):
  """Normalizes a backtrace for more accurate aggregation."""
  lines = backtrace.splitlines()
  normalizedLines = []
  for line in lines:
    if not line.lstrip().startswith('at sun.reflect.'):
      line = REMOVE_JAVA_MESSAGE.sub(lambda match: match.group(1), line)
      line = REMOVE_PYTHON_MESSAGE.sub(lambda match: match.group(1), line)
      line = REMOVE_OBJECTIVE_C_ADDRESS.sub(' ', line)
      normalizedLines.append(line)
  return '\n'.join(normalizedLines)
