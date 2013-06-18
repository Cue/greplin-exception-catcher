/*
 * Copyright 2011 The greplin-exception-catcher Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.greplin.gec;


import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.lang.exception.ExceptionUtils;
import org.apache.log4j.Level;
import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;

import java.io.IOException;
import java.io.StringWriter;

/**
 * Tests for the GecAppender.
 */
public class GecLog4jAppenderTest {
  private static final String ENVIRONMENT = "prod";
  private static final String PROJECT = "secretTown";
  private static final String SERVER_NAME = "secretTown FE 1";
  private static final String LOG_MESSAGE = "Error while rendering request";
  private static final String MESSAGE = "Illegal in 50 states";
  private static final String TYPE = IllegalArgumentException.class.getCanonicalName();

  GecLog4jAppender appender;


  @Before
  public void setUp() {
    this.appender = new GecLog4jAppender();
    this.appender.setEnvironment(ENVIRONMENT);
    this.appender.setProject(PROJECT);
    this.appender.setServerName(SERVER_NAME);
  }

  @Test
  public void testGecAppender() throws IOException {
    try {
      throw new IllegalArgumentException(MESSAGE);
    } catch (IllegalArgumentException e) {
      StringWriter writer = new StringWriter();
      this.appender.writeFormattedException(LOG_MESSAGE, e, Level.ERROR, writer);

      JsonNode root = parseJson(writer.toString());
      assertField(root, "project", PROJECT);
      assertField(root, "environment", ENVIRONMENT);
      assertField(root, "serverName", SERVER_NAME);
      assertField(root, "backtrace", ExceptionUtils.getStackTrace(e));
      assertField(root, "message", MESSAGE);
      assertField(root, "logMessage", LOG_MESSAGE);
      assertField(root, "type", TYPE);
    }
  }

  @Test
  public void testNonExceptionAppender() throws IOException {
    StringWriter writer = new StringWriter();
    this.appender.writeFormattedException("Error while rendering request", Level.ERROR, writer);

    JsonNode root = parseJson(writer.toString());
    assertField(root, "project", PROJECT);
    assertField(root, "environment", ENVIRONMENT);
    assertField(root, "serverName", SERVER_NAME);
    assertField(root, "message", LOG_MESSAGE);
    assertField(root, "logMessage", LOG_MESSAGE);
    assertField(root, "type", "N/A");
    String backtrace = root.path("backtrace").asText();
    Assert.assertTrue(backtrace.contains("testNonExceptionAppender"));
    Assert.assertFalse(backtrace.contains("writeFormattedException"));
  }


  /**
   * Parse a JSON string in to a JsonNode.
   * @param json the string
   * @return the node
   * @throws IOException should never happen
   */
  private JsonNode parseJson(String json) throws IOException {
    return new ObjectMapper().readTree(json);
  }


  /**
   * Assert that the given field has the given value.
   * @param root the root of the JSON tree
   * @param field the field name
   * @param value the expected value
   */
  private void assertField(JsonNode root, String field, String value) {
    Assert.assertEquals(value, root.path(field).asText());
  }
}
