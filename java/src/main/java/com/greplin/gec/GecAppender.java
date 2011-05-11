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

import org.apache.commons.lang.exception.ExceptionUtils;
import org.apache.log4j.AppenderSkeleton;
import org.apache.log4j.Level;
import org.apache.log4j.spi.LoggingEvent;
import org.codehaus.jackson.JsonFactory;
import org.codehaus.jackson.JsonGenerator;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.Writer;
import java.lang.reflect.InvocationTargetException;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;


/**
 * log4j appender that writes exceptions to a file.
 */
public final class GecAppender extends AppenderSkeleton {
  /**
   * Name of the project we are logging exceptions for.
   */
  private String project;

  /**
   * Name of the environment (prod/devel/etc.) we are logging exceptions in.
   */
  private String environment;

  /**
   * The name of this server.
   */
  private String serverName;

  /**
   * The directory to write exception files.
   */
  private String outputDirectory;


  /**
   * Set of classes that only exist to contain exceptions.
   */
  private final Set<Class<? extends Throwable>> passthroughExceptions;

  /**
   * Creates a new appender.
   */
  public GecAppender() {
    setThreshold(Level.ERROR);
    passthroughExceptions = new HashSet<Class<? extends Throwable>>();
    passthroughExceptions.add(InvocationTargetException.class);
  }

  @Override
  protected void append(final LoggingEvent loggingEvent) {
    UUID uniqueId = UUID.randomUUID();
    try {
      String filename = uniqueId.toString() + ".gec.json";
      File output = new File(outputDirectory, filename + ".writing");
      Writer writer = new FileWriter(output);

      if (loggingEvent.getThrowableInformation() == null) {
        writeFormattedException(loggingEvent.getRenderedMessage(), writer);
      } else {
        Throwable throwable =
            loggingEvent.getThrowableInformation().getThrowable();
        writeFormattedException(
            loggingEvent.getRenderedMessage(), throwable, writer);
      }

      writer.close();

      if (!output.renameTo(new File(outputDirectory, filename))) {
        System.err.println("Could not rename to " + filename);
      }
    } catch (IOException e) {
      e.printStackTrace();
    }
  }

  @Override
  public void close() {
  }

  @Override
  public boolean requiresLayout() {
    return false;
  }

  /**
   * Writes the current context to the given JsonGenerator.
   * @param generator where to write the context
   * @throws IOException if there are IO errors in the destination
   */
  private void writeContext(final JsonGenerator generator) throws IOException {
    Map<String, String> context = GecContext.get();
    if (!context.isEmpty()) {
      generator.writeFieldName("context");
      generator.writeStartObject();
      for (Map.Entry<String, String> entry : context.entrySet()) {
        generator.writeStringField(entry.getKey(), entry.getValue());
      }
      generator.writeEndObject();
    }
  }

  /**
   * Writes a formatted msg for errors that don't have exceptions.
   *
   * @param message the log message
   * @param out     the destination
   * @throws IOException if there are IO errors in the destination
   */
  void writeFormattedException(final String message,
                               final Writer out)
      throws IOException {
    JsonGenerator generator = new JsonFactory().createJsonGenerator(out);

    String backtrace = ExceptionUtils.getFullStackTrace(new Exception());
    String[] lines = backtrace.split("\n");
    StringBuilder builder = new StringBuilder();
    for (String line : lines) {
      if (!line.contains("com.greplin.gec.GecAppender.")) {
        builder.append(line);
        builder.append("\n");
      }
    }
    backtrace = builder.toString();

    generator.writeStartObject();
    generator.writeStringField("project", project);
    generator.writeStringField("environment", environment);
    generator.writeStringField("serverName", serverName);
    generator.writeStringField("backtrace", backtrace);
    generator.writeStringField("message", message);
    generator.writeStringField("logMessage", message);
    generator.writeStringField("type", "N/A");
    writeContext(generator);
    generator.writeEndObject();
    generator.close();
  }

  /**
   * Writes a formatted exception to the given writer.
   *
   * @param message   the log message
   * @param throwable the exception
   * @param out       the destination
   * @throws IOException if there are IO errors in the destination
   */
  void writeFormattedException(final String message,
                               final Throwable throwable,
                               final Writer out)
      throws IOException {
    JsonGenerator generator = new JsonFactory().createJsonGenerator(out);

    Throwable rootThrowable = throwable;
    while (passthroughExceptions.contains(rootThrowable.getClass())
        && rootThrowable.getCause() != null) {
      rootThrowable = rootThrowable.getCause();
    }

    generator.writeStartObject();
    generator.writeStringField("project", project);
    generator.writeStringField("environment", environment);
    generator.writeStringField("serverName", serverName);
    generator.writeStringField("backtrace",
        ExceptionUtils.getStackTrace(throwable));
    generator.writeStringField("message", rootThrowable.getMessage());
    generator.writeStringField("logMessage", message);
    generator.writeStringField("type", rootThrowable.getClass().getName());
    writeContext(generator);
    generator.writeEndObject();
    generator.close();
  }

  /**
   * Sets the environment.
   *
   * @param environment the new environment
   */
  public void setEnvironment(final String environment) {
    this.environment = environment;
  }

  /**
   * Sets the project.
   *
   * @param project the new project
   */
  public void setProject(final String project) {
    this.project = project;
  }

  /**
   * Sets the server name.
   *
   * @param serverName the new server name
   */
  public void setServerName(final String serverName) {
    this.serverName = serverName;
  }

  /**
   * Sets the output directory.
   *
   * @param outputDirectory the new output directory
   */
  public void setOutputDirectory(final String outputDirectory) {
    this.outputDirectory = outputDirectory;
  }

  /**
   * Adds a class that can be considered a container of exceptions only.
   *
   * @param exceptionClass the exception class
   */
  public void addPassthroughExceptionClass(
      final Class<? extends Throwable> exceptionClass) {
    passthroughExceptions.add(exceptionClass);
  }
}
