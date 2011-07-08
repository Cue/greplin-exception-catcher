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

"""Sets up for deployment / development.  Should be run whenever config.json is changed."""

import shutil
import sys

try:
  from django.utils import simplejson as json
except ImportError:
  import json



def main():
  """Sets up for deployment / development."""
  if len(sys.argv) > 1:
    shutil.copy(sys.argv[1], 'config.json')
  with open('config.json') as f:
    config = json.load(f)

  for filename in ['app.yaml', 'index.yaml']:
    with open(filename + '.template') as f:
      template = f.read()
    template = template.replace('<id>', config['id'])
    template = template.replace('<version>', str(config.get('datastoreVersion', 2)))
    with open(filename, 'w') as f:
      f.write(template)




if __name__ == '__main__':
  main()
