#!/usr/bin/env python
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

"""Setup script for greplin.gec.logHandler."""

try:
  from setuptools import setup
except ImportError:
  from distutils.core import setup

setup(name='gec-logging-handler',
      version='0.1',
      description='Exception catching for Python\'s standard logging',
      license='Apache',
      author='Greplin, Inc.',
      author_email='opensource@greplin.com',
      url='https://www.github.com/Cue/greplin-exception-catcher',
      packages = [ 'greplin' ],
      namespace_packages = [ 'greplin' ],
      py_modules = [
        'greplin.gec.logHandler'
      ],
      zip_safe = True
)
