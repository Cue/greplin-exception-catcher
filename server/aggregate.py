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

# pylint: disable=E0611
from google.appengine.dist import use_library
use_library('django', '1.2')

from datamodel import    LoggedErrorInstance, AggregatedStats
from datetime import datetime, timedelta

from google.appengine.api.datastore_errors import Timeout

import collections
try:
  from django.utils import simplejson as json
except ImportError:
  import json
import logging


def entry():
  """Creates an empty error entry."""
  return {
    'count': 0,
    'servers': collections.defaultdict(int),
    'environments': collections.defaultdict(int)
  }


def aggregate(aggregation, instance):
  """Aggregates an instance in to the global stats."""
  item = aggregation[str(instance.error.key())]
  item['count'] += 1
  item['servers'][instance.server] += 1
  item['environments'][instance.environment] += 1


def retryingIter(queryGenerator):
  """Iterator with retry logic."""
  lastCursor = None
  for i in range(100):
    query = queryGenerator()
    if lastCursor:
      query.with_cursor(lastCursor)
    try:
      for item in query:
        lastCursor = query.cursor()
        yield item
    except Timeout:
      logging.info('Attempt #%d failed', i)


def main():
  """Runs the aggregation."""
  logging.info('running the cron')
  now = datetime.now()
  oneDayAgo = now - timedelta(days = 1)

  aggregation = collections.defaultdict(entry)

  count = 0
  query = lambda: LoggedErrorInstance.all().filter('date >=', oneDayAgo)
  for instance in retryingIter(query):
    aggregate(aggregation, instance)
    count += 1
    if not count % 500:
      logging.info('Finished %d items', count)
  result = sorted(aggregation.items(), key=lambda item: item[1]['count'], reverse=True)

  logging.info('Finished first day of data')

#  query = lambda: LoggedErrorInstance.all().filter('date <', oneDayAgo).filter('date >=', oneWeekAgo)
#  for instance in retryingIter(query):
#    aggregate(aggregation, instance)
#    count += 1
#    if not count % 500:
#      logging.info('Finished %d items', count)
#  result['week'] = sorted(aggregation.items(), key=lambda item: item[1]['count'], reverse=True)
#
#  logging.info('Finished first week of data')

  stat = AggregatedStats()
  stat.date = now
  stat.json = json.dumps(result)
  stat.put()

  logging.info('Put aggregate')


if __name__ == '__main__':
  main()

