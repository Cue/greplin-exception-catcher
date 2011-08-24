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

"""Tests for backtrace normalization."""

import unittest

import backtrace

EXAMPLE = """
java.lang.reflect.InvocationTargetException
	at sun.reflect.GeneratedMethodAccessor24.invoke(Unknown Source)
	at sun.reflect.DelegatingMethodAccessorImpl.invoke(DelegatingMethodAccessorImpl.java:43)
	at java.lang.reflect.Method.invoke(Method.java:616)
	at javax.servlet.http.HttpServlet.service(HttpServlet.java:637)
	at javax.servlet.http.HttpServlet.service(HttpServlet.java:717)
	at org.apache.catalina.core.ApplicationFilterChain.internalDoFilter(ApplicationFilterChain.java:290)
	at org.apache.catalina.core.ApplicationFilterChain.doFilter(ApplicationFilterChain.java:206)
	at org.apache.catalina.core.ApplicationFilterChain.internalDoFilter(ApplicationFilterChain.java:235)
	at org.apache.catalina.core.ApplicationFilterChain.doFilter(ApplicationFilterChain.java:206)
	at org.apache.catalina.core.ApplicationFilterChain.internalDoFilter(ApplicationFilterChain.java:235)
	at org.apache.catalina.core.ApplicationFilterChain.doFilter(ApplicationFilterChain.java:206)
	at org.apache.catalina.core.StandardWrapperValve.invoke(StandardWrapperValve.java:233)
	at org.apache.catalina.core.StandardContextValve.invoke(StandardContextValve.java:191)
	at org.apache.catalina.core.StandardHostValve.invoke(StandardHostValve.java:127)
	at org.apache.catalina.valves.ErrorReportValve.invoke(ErrorReportValve.java:102)
	at org.apache.catalina.core.StandardEngineValve.invoke(StandardEngineValve.java:109)
	at org.apache.catalina.connector.CoyoteAdapter.service(CoyoteAdapter.java:298)
	at org.apache.coyote.http11.Http11AprProcessor.process(Http11AprProcessor.java:865)
	at org.apache.coyote.http11.Http11AprProtocol$Http11ConnectionHandler.process(Http11AprProtocol.java:579)
	at org.apache.tomcat.util.net.AprEndpoint$Worker.run(AprEndpoint.java:1555)
	at java.lang.Thread.run(Thread.java:636)
Caused by: com.whatever.InterestingException: Can't do something for user #12345
  at com.whatever.SomeClass.method1(SomeClass.java:123)
	at com.whatever.SomeClass.method2(SomeClass.java:1123)
	at com.whatever.SomeClass.method3(SomeClass.java:2123)
	at com.whatever.SomeClass.method4(SomeClass.java:3123)
	... 26 more
Caused by: java.io.IOException: Map failed
	at sun.nio.ch.FileChannelImpl.map(FileChannelImpl.java:803)
	... 30 more
Caused by: java.lang.OutOfMemoryError: Map failed
	at sun.nio.ch.FileChannelImpl.map0(Native Method)
	at sun.nio.ch.FileChannelImpl.map(FileChannelImpl.java:800)
	... 36 more
"""


PYTHON_EXAMPLE = """
Traceback (most recent call last):
  File "/usr/local/lib/python2.6/dist-packages/tornado/web.py", line 789, in wrapper
    return callback(*args, **kwargs)
  File "/var/blah/src/deedah/handler/kabam.py", line 109, in _on_result
    raise exceptions.HttpException(500, "HTTP error: %s" % response.error)
HttpException: (500, 'HTTP error: HTTP 599: Operation timed out after 20314 milliseconds with 0 bytes received')
"""


OBJECTIVE_C_EXAMPLE = """
0   Greplin                             0x0008f1d7 Greplin + 582103
1   Greplin                             0x0008f449 Greplin + 582729
2   Greplin                             0x0008f315 Greplin + 582421
3   Greplin                             0x0008f2ed Greplin + 582381
4   Greplin                             0x000ba757 Greplin + 759639
5   CoreFoundation                      0x36accf03 -[NSObject(NSObject) performSelector:withObject:] + 22
6   Foundation                          0x34f987a9 __NSThreadPerformPerform + 268
7   CoreFoundation                      0x36b36a79 __CFRUNLOOP_IS_CALLING_OUT_TO_A_SOURCE0_PERFORM_FUNCTION__ + 12
8   CoreFoundation                      0x36b3875f __CFRunLoopDoSources0 + 382
9   CoreFoundation                      0x36b394eb __CFRunLoopRun + 230
10  CoreFoundation                      0x36ac9ec3 CFRunLoopRunSpecific + 230
11  CoreFoundation                      0x36ac9dcb CFRunLoopRunInMode + 58
12  GraphicsServices                    0x3628341f GSEventRunModal + 114
13  GraphicsServices                    0x362834cb GSEventRun + 62
14  UIKit                               0x35973d69 -[UIApplication _run] + 404
15  UIKit                               0x35971807 UIApplicationMain + 670
16  Greplin                             0x000028a3 Greplin + 6307
17  Greplin                             0x00002780 Greplin + 6016
"""


OBJECTIVE_C_EXAMPLE_SAME = """
0   Greplin                             0x0008f1d7 Greplin + 582103
1   Greplin                             0x0008f449 Greplin + 582729
2   Greplin                             0x0008f315 Greplin + 582421
3   Greplin                             0x0008f2ed Greplin + 582381
4   Greplin                             0x000ba757 Greplin + 759639
5   CoreFoundation                      0x349e9f03 -[NSObject(NSObject) performSelector:withObject:] + 22
6   Foundation                          0x3608e7a9 __NSThreadPerformPerform + 268
7   CoreFoundation                      0x34a53a79 __CFRUNLOOP_IS_CALLING_OUT_TO_A_SOURCE0_PERFORM_FUNCTION__ + 12
8   CoreFoundation                      0x34a5575f __CFRunLoopDoSources0 + 382
9   CoreFoundation                      0x34a564eb __CFRunLoopRun + 230
10  CoreFoundation                      0x349e6ec3 CFRunLoopRunSpecific + 230
11  CoreFoundation                      0x349e6dcb CFRunLoopRunInMode + 58
12  GraphicsServices                    0x3360d41f GSEventRunModal + 114
13  GraphicsServices                    0x3360d4cb GSEventRun + 62
14  UIKit                               0x33644d69 -[UIApplication _run] + 404
15  UIKit                               0x33642807 UIApplicationMain + 670
16  Greplin                             0x000028a3 Greplin + 6307
17  Greplin                             0x00002780 Greplin + 6016
"""


OBJECTIVE_C_EXAMPLE_NOT_SAME = """
0   Greplin                             0x0008f1d7 Greplin + 582103
1   Greplin                             0x0008f449 Greplin + 582729
2   Greplin                             0x0008f401 Greplin + 582657
3   Greplin                             0x0000296b Greplin + 6507
4   libsystem_c.dylib                   0x33e3c727 _sigtramp + 34
5   libsystem_kernel.dylib              0x33df575f mach_msg + 50
6   CoreFoundation                      0x361272bf __CFRunLoopServiceMachPort + 94
7   CoreFoundation                      0x36129569 __CFRunLoopRun + 356
8   CoreFoundation                      0x360b9ec3 CFRunLoopRunSpecific + 230
9   CoreFoundation                      0x360b9dcb CFRunLoopRunInMode + 58
10  Foundation                          0x345237fd +[NSURLConnection(NSURLConnectionReallyInternal) _resourceLoadLoop:] + 212
11  Foundation                          0x34516389 -[NSThread main] + 44
12  Foundation                          0x345885cd __NSThread__main__ + 972
13  libsystem_c.dylib                   0x33e31311 _pthread_start + 248
14  libsystem_c.dylib                   0x33e32bbc start_wqthread + 0
"""



class BacktraceTestCase(unittest.TestCase):
  """Tests for backtrace normalization."""

  def testRemoveCauseMessage(self):
    """Test that cause messages are removed."""
    differentMessage = EXAMPLE.replace('12345', '23456')
    self.assertEquals(backtrace.normalizeBacktrace(EXAMPLE), backtrace.normalizeBacktrace(differentMessage))

    differentError = EXAMPLE.replace('SomeClass', 'SomeOtherClass')
    self.assertNotEquals(backtrace.normalizeBacktrace(EXAMPLE), backtrace.normalizeBacktrace(differentError))


  def testSlightlyDifferentInvokes(self):
    """Test that slightly different reflection based invocations lead to the same result."""
    differentMessage = EXAMPLE.replace('24.invoke', '24.invoke0')
    self.assertEquals(backtrace.normalizeBacktrace(EXAMPLE), backtrace.normalizeBacktrace(differentMessage))

    differentError = EXAMPLE.replace('.method4', '.methodNot4AtAll')
    self.assertNotEquals(backtrace.normalizeBacktrace(EXAMPLE), backtrace.normalizeBacktrace(differentError))


  def testPythonCauseMessage(self):
    """Test that cause messages are removed for Python."""
    differentMessage = PYTHON_EXAMPLE.replace('HTTP 599', 'HTTP 404')
    self.assertEquals(backtrace.normalizeBacktrace(PYTHON_EXAMPLE), backtrace.normalizeBacktrace(differentMessage))

    differentMessage = PYTHON_EXAMPLE.replace('HttpException:', 'OtherException:')
    self.assertNotEquals(backtrace.normalizeBacktrace(PYTHON_EXAMPLE), backtrace.normalizeBacktrace(differentMessage))


  def testObjectiveCAddresses(self):
    """Test that addresses are removed for Objective C."""
    self.assertEquals(backtrace.normalizeBacktrace(OBJECTIVE_C_EXAMPLE),
                      backtrace.normalizeBacktrace(OBJECTIVE_C_EXAMPLE_SAME))
    self.assertNotEquals(backtrace.normalizeBacktrace(OBJECTIVE_C_EXAMPLE),
                         backtrace.normalizeBacktrace(OBJECTIVE_C_EXAMPLE_NOT_SAME))