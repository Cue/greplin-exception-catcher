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

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonGenerator;
import org.apache.commons.lang.exception.ExceptionUtils;
import org.apache.log4j.AppenderSkeleton;
import org.apache.log4j.Level;
import org.apache.log4j.spi.LoggingEvent;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.Writer;
import java.lang.reflect.InvocationTargetException;
import java.util.HashSet;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;


/**
 * log4j appender that writes exceptions to a file to be picked up by upload.py.
 */
public final class GecLog4jAppender extends AppenderSkeleton {
  /**
   * Number of prefixes to use to reduce risk of server invocations overwriting
   * each other's error logs.
   */
  private static final int MAX_BASENAME = 10;

  /**
   * Maximum number of errors a single instance of the server can write.
   */
  private static final int MAX_ERRORS = 10000;

  /**
   * Base name for error files.  Used to reduce risk of server invocations
   * clobbering each other's error logs.
   */
  private static final String BASENAME;

  /**
   * ID for the next error will be this value modulo MAX_ERRORS.
   */
  private static final AtomicLong ERROR_ID;

  static {
    Random random = new Random();
    // We randomly choose a base name and starting number to minimize the risk
    // of multiple invocations of a server overwriting error logs.
    BASENAME = random.nextInt(MAX_BASENAME) + "-";
    ERROR_ID = new AtomicLong(random.nextInt(MAX_ERRORS));
  }

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
  public GecLog4jAppender() {
    setThreshold(Level.ERROR);
    this.passthroughExceptions = new HashSet<Class<? extends Throwable>>();
    this.passthroughExceptions.add(InvocationTargetException.class);
  }

  @Override
  protected void append(final LoggingEvent loggingEvent) {
    try {
      if (loggingEvent.getThrowableInformation() == null
          && loggingEvent.getLevel().toInt() < this.threshold.toInt()) {
        // Ignore non-exceptions below our threshold.
        return;
      }

      String errorId = BASENAME + (ERROR_ID.incrementAndGet() % MAX_ERRORS);
      String filename = errorId + ".gec.json";
      File output = new File(this.outputDirectory, filename + ".writing");
      Writer writer = new FileWriter(output);

      if (loggingEvent.getThrowableInformation() == null) {
        writeFormattedException(
            loggingEvent.getRenderedMessage(),
            loggingEvent.getLevel(),
            writer);
      } else {
        Throwable throwable =
            loggingEvent.getThrowableInformation().getThrowable();
        writeFormattedException(
            loggingEvent.getRenderedMessage(),
            throwable,
            loggingEvent.getLevel(),
            writer);
      }

      writer.close();

      if (!output.renameTo(new File(this.outputDirectory, filename))) {
        System.err.println("Could not rename to " + filename);
      }
    } catch (IOException e) {
      System.err.println("GEC failed to append: " + e.getMessage());
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
  private void writeContext(final JsonGenerator  generator) throws IOException {
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
   * @param level   the error level
   * @param out     the destination
   * @throws IOException if there are IO errors in the destination
   */
  void writeFormattedException(final String message,
                               final Level level,
                               final Writer out)
      throws IOException {
    JsonGenerator generator = new JsonFactory().createJsonGenerator(out);

    String backtrace = ExceptionUtils.getFullStackTrace(new Exception());
    String[] lines = backtrace.split("\n");
    StringBuilder builder = new StringBuilder();
    for (String line : lines) {
      if (!line.contains("com.greplin.gec.GecLog4jAppender.")) {
        builder.append(line);
        builder.append("\n");
      }
    }
    backtrace = builder.toString();

    generator.writeStartObject();
    generator.writeStringField("project", this.project);
    generator.writeStringField("environment", this.environment);
    generator.writeStringField("serverName", this.serverName);
    generator.writeStringField("backtrace", backtrace);
    generator.writeStringField("message", message);
    generator.writeStringField("logMessage", message);
    generator.writeStringField("type", "N/A");
    if (level != Level.ERROR) {
      generator.writeStringField("errorLevel", level.toString());
    }
    writeContext(generator);
    generator.writeEndObject();
    generator.close();
  }

  /**
   * Writes a formatted exception to the given writer.
   *
   * @param message   the log message
   * @param throwable the exception
   * @param level     the error level
   * @param out       the destination
   * @throws IOException if there are IO errors in the destination
   */
  void writeFormattedException(final String message,
                               final Throwable throwable,
                               final Level level,
                               final Writer out)
      throws IOException {
    JsonGenerator generator = new JsonFactory().createJsonGenerator(out);

    Throwable rootThrowable = throwable;
    while (this.passthroughExceptions.contains(rootThrowable.getClass())
        && rootThrowable.getCause() != null) {
      rootThrowable = rootThrowable.getCause();
    }

    generator.writeStartObject();
    generator.writeStringField("project", this.project);
    generator.writeStringField("environment", this.environment);
    generator.writeStringField("serverName", this.serverName);
    generator.writeStringField("backtrace",
        ExceptionUtils.getStackTrace(throwable));
    generator.writeStringField("message", rootThrowable.getMessage());
    generator.writeStringField("logMessage", message);
    generator.writeStringField("type", rootThrowable.getClass().getName());
    if (level != Level.ERROR) {
      generator.writeStringField("errorLevel", level.toString());
    }
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
    this.passthroughExceptions.add(exceptionClass);
  }


  /**
   * Adds a class that can be considered a container of exceptions only.
   * Adds by name, but does not throw if the class is not found.
   *
   * @param name the exception class
   * @return true if the class exists and was added, false otherwise
   */
  @SuppressWarnings("unchecked")
  public boolean addPassthroughExceptionClass(final String name) {
    try {
      addPassthroughExceptionClass(
          (Class<? extends Throwable>) Class.forName(name));
    } catch (ClassNotFoundException ex) {
      return false;
    }
    return true;
  }

}
