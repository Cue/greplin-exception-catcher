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

"""AppEngine server for aggregating exceptions."""

from datamodel import    LoggedErrorInstance, AggregatedStats
from datetime import datetime, timedelta

import collections

try:
  from django.utils import simplejson as json
except ImportError:
  import json



def entry():
  """Creates an empty error entry."""
  return {
    'count': 0,
    'servers': collections.defaultdict(int),
    'environments': collections.defaultdict(int)
  }


def aggregate(aggregation, instance):
  """Aggregates an instance in to the global stats."""
  item = aggregation[str(instance.parent_key())]
  item['count'] += 1
  item['servers'][instance.server] += 1
  item['environments'][instance.environment] += 1



def main():
  """Runs the aggregation."""
  now = datetime.now()
  oneDayAgo = now - timedelta(days = 1)
  oneWeekAgo = now - timedelta(days = 7)

  result = {}
  aggregation = collections.defaultdict(entry)

  query = LoggedErrorInstance.all().filter('date >=', oneDayAgo)
  for instance in query:
    aggregate(aggregation, instance)
  result['day'] = sorted(aggregation.items(), key=lambda item: item[1]['count'], reverse=True)

  query = LoggedErrorInstance.all().filter('date <', oneDayAgo).filter('date >=', oneWeekAgo)
  for instance in query:
    aggregate(aggregation, instance)
  result['week'] = sorted(aggregation.items(), key=lambda item: item[1]['count'], reverse=True)

  stat = AggregatedStats()
  stat.date = now
  stat.json = json.dumps(result)
  stat.put()


if __name__ == '__main__':
  main()

