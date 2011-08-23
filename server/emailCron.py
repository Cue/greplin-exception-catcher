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

"""AppEngine server for emailing new exceptions."""

# pylint: disable=E0611
from google.appengine.dist import use_library
use_library('django', '1.2')

# pylint: disable=E0611
from google.appengine.api import mail
# pylint: disable=E0611
from google.appengine.ext.webapp import template

from common import getTemplatePath
import config
from datamodel import LoggedError

import collections
from datetime import datetime, timedelta
import logging



def main():
  """Runs the aggregation."""
  toEmail = config.get('toEmail')
  fromEmail = config.get('fromEmail')

  if toEmail and fromEmail:
    logging.info('running the email cron')

    errorQuery = (LoggedError.all().filter('active =', True)
        .filter('firstOccurrence >', datetime.now() - timedelta(hours = 24))
        .order('-firstOccurrence'))

    errors = errorQuery.fetch(500, 0)
    errors.sort(key = lambda x: x.count, reverse=True)

    projects = collections.defaultdict(list)
    for error in errors:
      projects[error.project.key().name()].append(error)

    context = {'projects': sorted(projects.items()), 'errorCount': len(errors), 'baseUrl': config.get('baseUrl')}

    body = template.render(getTemplatePath('dailymail.html'), context).strip()
    mail.send_mail(
        sender=fromEmail, to=toEmail, subject='Latest GEC reports', body='Only available in HTML', html=body)


if __name__ == '__main__':
  main()

