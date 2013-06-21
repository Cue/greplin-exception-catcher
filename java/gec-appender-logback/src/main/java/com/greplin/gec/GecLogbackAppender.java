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

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.classic.spi.IThrowableProxy;
import ch.qos.logback.classic.spi.StackTraceElementProxy;
import ch.qos.logback.classic.spi.ThrowableProxy;
import ch.qos.logback.classic.spi.ThrowableProxyUtil;
import ch.qos.logback.core.AppenderBase;
import ch.qos.logback.core.CoreConstants;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonGenerator;

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
public final class GecLogbackAppender extends AppenderBase<ILoggingEvent> {
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
  private final Set<String> passthroughExceptions;

  /**
   * Creates a new appender.
   */
  public GecLogbackAppender() {
    // setThreshold(Level.ERROR); // FIXME: replaced by filters ?
    this.passthroughExceptions = new HashSet<String>();
    this.passthroughExceptions.add(
        InvocationTargetException.class.getCanonicalName());
  }

  @Override
  public void start() {
    /* FIXME outdated docs ?
    if (this.layout == null) {
      addError("No layout set for the appender named [" + name + "].");
      return;
    }
    */
    super.start();
  }

  @Override
  protected void append(final ILoggingEvent loggingEvent) {

    try {
      if (loggingEvent.getThrowableProxy() == null
          && loggingEvent.getLevel().toInt() < Level.ERROR_INT) {
        // Ignore non-exceptions below our threshold.
        return;
      }

      String errorId = BASENAME + (ERROR_ID.incrementAndGet() % MAX_ERRORS);
      String filename = errorId + ".gec.json";
      File output = new File(this.outputDirectory, filename + ".writing");
      Writer writer = new FileWriter(output);

      if (loggingEvent.getThrowableProxy() == null) {
        writeFormattedException(
            loggingEvent.getMessage(),
            loggingEvent.getLevel(),
            writer);
      } else {
        writeFormattedException(
            loggingEvent.getMessage(),
            loggingEvent.getThrowableProxy(),
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

    String backtrace = GecLogbackAppender.getStackTrace(new Throwable());
    String[] lines = backtrace.split("\n");
    StringBuilder builder = new StringBuilder();
    for (String line : lines) {
      if (!line.contains("com.greplin.gec.GecLogbackAppender.")) {
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
                               final Writer out) throws IOException {
    this.writeFormattedException(message,
        new ThrowableProxy(throwable), level, out);
  }

  /**
   * Writes a formatted exception to the given writer.
   *
   * @param message   the log message
   * @param throwableProxy the exception
   * @param level     the error level
   * @param out       the destination
   * @throws IOException if there are IO errors in the destination
   */
  private void writeFormattedException(final String message,
                                       final IThrowableProxy throwableProxy,
                                       final Level level,
                                       final Writer out)
      throws IOException {
    JsonGenerator generator = new JsonFactory().createJsonGenerator(out);

    IThrowableProxy rootThrowable = throwableProxy;
    while (this.passthroughExceptions.contains(rootThrowable.getClassName())
        && rootThrowable.getCause() != null) {
      rootThrowable = rootThrowable.getCause();
    }

    generator.writeStartObject();
    generator.writeStringField("project", this.project);
    generator.writeStringField("environment", this.environment);
    generator.writeStringField("serverName", this.serverName);
    // FIXME this was 'throwable'
    generator.writeStringField("backtrace", getStackTrace(rootThrowable));
    generator.writeStringField("message", rootThrowable.getMessage());
    generator.writeStringField("logMessage", message);
    generator.writeStringField("type", rootThrowable.getClassName());
    if (level != Level.ERROR) {
      generator.writeStringField("errorLevel", level.toString());
    }
    writeContext(generator);
    generator.writeEndObject();
    generator.close();
  }


  /**
   * Renders a stacktrace.
   * @param throwableProxy an IThrowableProxy
   * @return a string rendering of the stack trace
   */
  protected static String getStackTrace(final IThrowableProxy throwableProxy) {
    StringBuilder builder = new StringBuilder();
    for (StackTraceElementProxy step
        : throwableProxy.getStackTraceElementProxyArray()) {
      String string = step.toString();
      builder.append(CoreConstants.TAB).append(string);
      ThrowableProxyUtil.subjoinPackagingData(builder, step);
      builder.append(CoreConstants.LINE_SEPARATOR);
    }
    return builder.toString();
  }

  /**
   * Renders a stacktrace.
   * @param t a throwable
   * @return a string rendering of the stack trace
   */
  protected static String getStackTrace(final Throwable t) {
    return GecLogbackAppender.getStackTrace(new ThrowableProxy(t));
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
    this.passthroughExceptions.add(exceptionClass.getCanonicalName());
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
