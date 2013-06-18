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

import java.util.HashMap;
import java.util.Map;

/**
 * ThreadLocal context for GEC.
 * Note: duplicated in both gec-appender-log4j and gec-appender-logback.
 * Really should be in a third module, but this feels overkill right now.
 */
public final class GecContext {
  /**
   * Not instantiable.
   */
  private GecContext() {
  }


  /**
   * Thread-local context map.
   */
  private static ThreadLocal<Map<String, String>> contextPerThread =
      new ThreadLocal<Map<String, String>>() {
        protected synchronized Map<String, String> initialValue() {
          return new HashMap<String, String>();
        }
      };


  /**
   * Gets the entire context of the current thread.
   * @return the context
   */
  static Map<String, String> get() {
    return contextPerThread.get();
  }


  /**
   * Sets a context value.
   * @param key the key
   * @param value the value for that key
   */
  public static void put(final String key, final String value) {
    contextPerThread.get().put(key, value);
  }


  /**
   * Clears the context.
   */
  public static void clear() {
    contextPerThread.get().clear();
  }
}
