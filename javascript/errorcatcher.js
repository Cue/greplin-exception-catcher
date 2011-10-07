/*
Copyright 2011 The greplin-exception-catcher Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
====

This Javascript file lets web applications get stacktraces for all uncaught JS exceptions and send them to Greplin
Exception Catcher.

Features include:
 - Stacktraces in IE 6-8, as well as modern versions of Firefox, Chrome, and Opera
 - Javascript execution entry point information (such as event type and listener) on IE 6-9 and modern versions of
   Firefox, Chrome, Safari, and Opera
 - Redaction of URLs and strings in stacktraces to avoid logging sensitive user information

Things that aren't done yet:
 - Aggregation. Due to the way GEC works now, this would be impossible to do without losing potentially useful
   information. To do this, GEC needs to be able to aggregate based upon a normalized stacktrace while still providing detailed information for each specific incident of the exception.
 - Can't wrap DOM0 events (<div onclick> for example).
 - Some code cleanup: Since this is a small, self-contained project, I took sort of a "hack it until it works" approach
   to coding it. I'd like to go back and structure the code better sometime, but I probably wont' get around to it
   anytime soon since it works very reliably as it is.

How to use it:
1. Create an endpoint at your server to send this stuff to GEC.
2. Modify the call to g.errorCatcher at the end of the file to pass in functions that pass exceptions to GEC and that
   redact URLs respectively. (Note: your URL redaction function will be passed strings that may contain URLs, not bare
   URLs, so keep that in mind)
3. Wrap your JS files if you want to capture errors during their initial execution:
    try {  var your_js_here  }
   catch(e) { window.g && g.handleInitialException && g.handleInitialException(e, '(script filename here)') }
    If you use Closure Compiler, just do
   --output_wrapper="window.COMPILED = true; try { %%output%% } catch(e) { window.g && g.handleInitialException && g.handleInitialException(e, '(script filename here)') }"
4. This exception catching script can't see exceptions that happen before it's loaded, so make sure it's loaded early in
   your page before most of your other scripts.

 */

var g = g || {};


/**
 * Captures uncaught JS exceptions on the page and passes them to GEC.
 * Can capture stacktraces in IE 6-8, Firefox, Chrome, and Opera, and can capture only the top of the stack in IE 9.
 * In Safari, only basic event information is captured.
 * Uses both window.onerror and wrapped DOM prototype interfaces to capture as much information as possible without
 * requiring JS code changes.
 */
g.errorCatcher = function(reportHandler, redactQueryStrings) {
  g.errorCatcher.reportHandler_ = reportHandler;
  g.errorCatcher.redactQueryStrings_ = redactQueryStrings;

  // commented out part is for weird cases where you have two exception catchers.
  // i haven't tested that case at all though, so i'm commenting it out for now.
  var wrappedProperty = 'WrappedListener'; //+ Math.floor(Math.random() * 10000000).toString(30);

  var supportsJsErrorStack;

  try {
    ({})['undefinedMethod']();
  } catch(error) {
    supportsJsErrorStack = 'stack' in error || 'stacktrace' in error;
  }

  var supportsWindowOnerror = 'onerror' in window && !/^Opera/.test(navigator.userAgent);

  var supportsWindowOnerrorStack = /MSIE /.test(navigator.userAgent);

  // Detecting support based on a whitelist sucks, but we don't want to accidentally log personal information, so we
  // only allow browsers that we know that we can redact stacktrace strings for.
  var supportsDOMWrapping =
    // Chrome
    /Chrom(e|ium)/.test(navigator.userAgent) ||

    // IE 9+
    /MSIE (9\.|[1-9][0-9]+\.)/.test(navigator.userAgent) || // XXX compat mode?

    // Firefox 6+
    /Gecko\/[0-9]/.test(navigator.userAgent) && (parseInt(navigator['buildID'], 10) >= 20110830092941) ||

    // Safari 5.1+ (AppleWebKit/534+)
    /AppleWebKit\/(53[4-9]|5[4-9][0-9]|[6-9][0-9]{2}|[1-9][0-9]{3})/.test(navigator.userAgent) ||

    // Opera 11.50+
    /^Opera.*Presto\/(2\.9|[3-9]|[1-9][0-9])/.test(navigator.userAgent);

  if (supportsDOMWrapping) {
    wrapTimeouts();
    wrapDOMEvents();
    wrapXMLHttpRequest();
  }

  if (supportsWindowOnerror &&
      (!supportsDOMWrapping || (!supportsJsErrorStack && supportsWindowOnerrorStack))) {
    window.onerror = function(errorMessage, url, lineNumber) {
      // Grab the error provided by DOM wrappings, if it's available
      var errorObject = g.errorCatcher.lastDomWrapperError_ || {};
      delete g.errorCatcher.lastDomWrapperError_;

      errorObject.message = errorObject.message || errorMessage;
      errorObject.url = errorObject.url || url;
      errorObject.line =  errorObject.line || lineNumber;

      // In IE, get the character offset inside the line of the error from window.event.
      if (window.event && typeof window.event['errorCharacter'] == 'number') {
        errorObject.character = (errorObject.character || window.event['errorCharacter']) + '';
      }

      // If there isn't already a stacktrace generated by the DOM wrappers, try to generate one using the old-fashioned
      // caller method. This only works in IE 6-8. It partially works in IE 9 -- but it only lets you get the top of the
      // stack.
      if (!errorObject.stacktrace && supportsWindowOnerrorStack) {
        try {
          errorObject.stacktrace = g.errorCatcher.getStacktrace(arguments.callee.caller);
        } catch(exception) {
          errorObject.stacktrace = '[error generating stacktrace: ' + exception.message + ']';
        }
      }

      g.errorCatcher.reportException(errorObject);
    };
  }

  /**
   * Wraps setTimeout and setInterval to handle uncaught exceptions in listeners.
   */
  function wrapTimeouts() {
    wrapTimeoutsHelper('setTimeout');
    wrapTimeoutsHelper('setInterval');
    function wrapTimeoutsHelper(timeoutMethodName) {
      var original = window[timeoutMethodName];
      window[timeoutMethodName] = function(listener, delay) {
        if (typeof listener == 'function') {
          var newArgs = Array.prototype.slice.call(arguments);
          newArgs[0] = function() {
            try {
              listener.apply(this, arguments);
            } catch(exception) {
              g.errorCatcher.handleCatchException(
                  exception, timeoutMethodName + '(' + g.errorCatcher.stringify(listener) + ', ' + delay + ')');
            }
          };
          return original.apply(this, newArgs);
        } else {
          // If someone passes a string to setTimeout, don't bother wrapping it.
          return original.apply(this, arguments);
        }
      }
    }
  }


  /**
   * Wraps DOM event interfaces (addEventListener and removeEventListener) to add try/catch wrappers to all event
   * listeners.
   */
  function wrapDOMEvents() {
    var eventsWrappedProperty = 'events' + wrappedProperty;

    wrapDOMEventsHelper(window.XMLHttpRequest.prototype);
    wrapDOMEventsHelper(window.Element.prototype);
    wrapDOMEventsHelper(window);
    wrapDOMEventsHelper(window.document);

    // Workaround for Firefox bug https://bugzilla.mozilla.org/show_bug.cgi?id=456151
    if (document.documentElement.addEventListener != window.Element.prototype.addEventListener) {
      var elementNames =
          ('Unknown,Anchor,Applet,Area,BR,Base,Body,Button,DList,Directory,Div,Embed,FieldSet,Font,Form,Frame,' +
           'FrameSet,HR,Head,Heading,Html,IFrame,Image,Input,IsIndex,LI,Label,Legend,Link,Map,Menu,Meta,Span,OList,' +
           'Object,OptGroup,Option,Paragraph,Param,Pre,Quote,Script,Select,Style,TableCaption,TableCell,TableCol,' +
           'Table,TableRow,TableSection,TextArea,Title,UList,Canvas').split(',');
      elementNames.forEach(function(elementName) {
        var constructor = window['HTML' + elementName + 'Element'];
        if (constructor && constructor.prototype) {
          wrapDOMEventsHelper(constructor.prototype);
        }
      });

    }

    function wrapDOMEventsHelper(object) {
      var originalAddEventListener = object.addEventListener;
      var originalRemoveEventListener = object.removeEventListener;
      if (!originalAddEventListener || !originalRemoveEventListener) {
        return;
      }
      object.addEventListener = function(eventType, listener, useCapture) {
        // Dedupe the listener in case it is already listening unwrapped.
        originalRemoveEventListener.apply(this, arguments);
        if (typeof listener != 'function') {
          // TODO(david): Handle a listener that is not a function, but instead an object that implements the
          // EventListener interface (see http://www.w3.org/TR/DOM-Level-2-Events/events.html#Events-EventListener ).
          originalAddEventListener.apply(this, arguments);
          return;
        }
        listener[eventsWrappedProperty] = listener[eventsWrappedProperty] || {
          innerListener: listener,
          'handleEvent': g.errorCatcher.listenerWrapper_
        };
        originalAddEventListener.call(this, eventType, listener[eventsWrappedProperty], useCapture);
      };
      object.removeEventListener = function(eventType, listener, useCapture) {
        // Remove unwrapped listener, just to be sure.
        originalRemoveEventListener.apply(this, arguments);
        if (typeof listener != 'function') {
          return;
        }
        if (listener[eventsWrappedProperty]) {
          originalRemoveEventListener.call(this, eventType, listener[eventsWrappedProperty], useCapture);
        }
      };
    }
  }


  /**
   * Wrap XMLHttpRequest onreadystatechange listeners to handle uncaught JS exceptions.
   * This only affects the .onreadystatechange property. The addEventListener property is handled by wrapDOMEvents.
   */
  function wrapXMLHttpRequest() {
    var xhrWrappedProperty = 'xhr' + wrappedProperty;
    var ctor = XMLHttpRequest, instance = new XMLHttpRequest;
    if (!/(AppleWebKit|MSIE)/.test(navigator.userAgent) ||
        (Object.getOwnPropertyDescriptor(ctor.prototype, 'onreadystatechange') || {}).configurable &&
         instance.__lookupSetter__ && instance.__lookupSetter__('onreadystatechange')) {
      // The browser has good support for manipulating XMLHttpRequest prototypes.
      var onreadystatechangeSetter = instance.__lookupSetter__('onreadystatechange');
      ctor.prototype.__defineGetter__('onreadystatechange', function() {
        return this[xhrWrappedProperty];
      });
      ctor.prototype.__defineSetter__('onreadystatechange', function(listener) {
        this[xhrWrappedProperty] = listener;
        onreadystatechangeSetter.call(this, wrappedReadyStateChange);
      });
    } else {
      // Chrome and Safari have problems with this. Instead, check to see if onreadystatechange needs to be wrapped
      // from a readystatechange event listener.
      var send = instance.send;
      var addEventListener = instance.addEventListener;
      XMLHttpRequest.prototype.send = function() {
        addEventListener.call(this, 'readystatechange', wrapReadyStateChange, true);
        return send.apply(this, arguments);
      }
    }
    function wrappedReadyStateChange() {
      try {
        var onreadystatechange =
            (this.onreadystatechange == arguments.callee ?
             this[xhrWrappedProperty] : this.onreadystatechange);
        this[xhrWrappedProperty].apply(this, arguments);
      } catch(exception) {
        // TODO(david): Expose some information about the xmlhttprequest to the exception logging (maybe request url)
        g.errorCatcher.handleCatchException(exception, 'onreadystatechange');
      }
    }
    // Used in the wrapped XHR::send handler to wrap onreadystatechange in response to addEventListener
    // readystatechange events that fire first.
    function wrapReadyStateChange() {
      if (this.onreadystatechange && this.onreadystatechange != wrappedReadyStateChange) {
        this[xhrWrappedProperty] = this.onreadystatechange;
        this.onreadystatechange = wrappedReadyStateChange;
      }
    }
  }
};


/**
 * Time that the last error was reported. Used for rate-limiting.
 * @type {number}
 */
g.errorCatcher.lastError_ = 0;


/**
 * Delay between reporting errors. Increases dynamically.
 * @type {number}
 */
g.errorCatcher.errorDelay_ = 10;


/**
 * Wrapper for addEventListener/removeEventListener listeners. Global to avoid potential memory/performance impacts of a
 * function closure for each event listener. This is a handleEvent property of the EventHandler object passed to
 * addEventListener. It accesses other properties of that object to read exception information.
 * @param {Event} eventObject The DOM event.
 */
g.errorCatcher.listenerWrapper_ = function(eventObject) {
  try {
    return this.innerListener.apply(eventObject.target, arguments);
  } catch(exception) {
    g.errorCatcher.handleCatchException(
        exception, eventObject.type + ' listener ' + g.errorCatcher.stringify(this.innerListener) + ' on ' +
            g.errorCatcher.stringify(eventObject.currentTarget));
  }
};


/**
 * Passes an exception to GEC.
 * TODO(david): show a message to the user. Let the user elect to send more detailed error information (un-redacted
 * strings).
 * @param {Object} errorObject An object describing the error.
 */
g.errorCatcher.reportException = function(errorObject) {
  var d = (new Date).getTime();
  if (d - g.errorCatcher.lastError_ < g.errorCatcher.errorDelay_) {
    // Rate limited
    return;
  }
  g.errorCatcher.lastError_ = d;
  g.errorCatcher.errorDelay_ = g.errorCatcher.errorDelay_ * 2;
  errorObj = {
      'msg':g.errorCatcher.redactQueryStrings_(errorObject.message || ''),
      'line': errorObject.line + (typeof errorObject.character == 'string' ? ':' + errorObject.character : ''),
      'trace':'Type: ' + errorObject.name + '\nUser-agent: ' + navigator.userAgent +
          '\nURL: ' + g.errorCatcher.redactQueryStrings_(location.href) + '\n\n' +
          g.errorCatcher.redactQueryStrings_(errorObject.stacktrace || ''),
      'ts': Math.floor(new Date().getTime() / 1000),
      'name':g.errorCatcher.redactQueryStrings_(errorObject.context || '') || 'unidentified JS thread'};
  g.errorCatcher.reportHandler_(errorObj);

};


/**
 * Handles exceptions from the try { } catch { } block added around all of our compiled JS by our Closure Compiler
 * configuration. This handles exceptions that occur during the intiial execution of the script.
 * @param {Error} caughtException The caught exception.
 * @param {string} fileName The name of the JS file where the exception occured.
 */
g.errorCatcher.handleInitialException = function(caughtException, fileName) {
  g.errorCatcher.handleCatchException(caughtException, 'Initial execution of ' + fileName);
};


/**
 * Handles a caught exception. When window.onerror is available, the exception is re-thrown so that additional
 * information from window.onerror can be added. Otherwise, the exception is passed to reportException, where it is
 * sent to GEC and potentially displayed to the user.
 * @param {Error} caughtException The caught JS exception.
 * @param context
 */
g.errorCatcher.handleCatchException = function(caughtException, context) {
  if (!(caughtException instanceof window.Error)) {
    caughtException = new Error(caughtException);
  }

  var errorObject = {};
  errorObject.context = context;
  errorObject.name = caughtException.name;
  // Opera has both stacktrace and stack. Stacktrace is much more detailed, so use that when available.
  errorObject.stacktrace = caughtException['stacktrace'] || caughtException['stack'];
  if (/Gecko/.test(navigator.userAgent) && !/AppleWebKit/.test(navigator.userAgent)) {
    errorObject.stacktrace = g.errorCatcher.redactFirefoxStacktraceStrings(errorObject.stacktrace);
  }
  errorObject.message = caughtException.message;
  errorObject.number = caughtException.number;

  var matches;
  if ('lineNumber' in caughtException) {
    errorObject.line = caughtException['lineNumber'];
  } else if ('line' in caughtException) {
    errorObject.line = caughtException['line'];
  } else if (/Chrom(e|ium)/.test(navigator.userAgent)) {
    matches = caughtException.stack.match(/\:(\d+)\:(\d+)\)(\n|$)/);
    if (matches) {
      errorObject.line = matches[1];
      errorObject.character = matches[2];
    }
  } else if (/Opera/.test(navigator.userAgent)) {
    matches = (errorObject['stacktrace'] || '').match(/Error thrown at line (\d+), column (\d+)/);
    if (matches) {
      errorObject.line = matches[1];
      errorObject.character = matches[2];
    } else {
      matches = (errorObject['stacktrace'] || '').match(/Error thrown at line (\d+)/);
      if (matches){
        errorObject.line = matches[1];
      }
    }
  }

  if (window.onerror) {
    // window.onerror is still needed to get stack in IE, so we need to re-throw the error to that.
    g.errorCatcher.lastDomWrapperError_ = errorObject;
    throw caughtException;
  } else {
    g.errorCatcher.reportException(errorObject);
  }
};


/**
 * @param {Function} opt_topFunction The function at the top of the stack; if omitted, the caller of makeStacktrace is
 *     used.
 * @return {string} A string showing the stack of functions and arguments.
 */
g.errorCatcher.getStacktrace = function(opt_topFunction) {
  var stacktrace = '';
  var func = opt_topFunction || arguments.callee.caller;
  var used = [];
  var length = 0;
  stacktraceLoop: do {
    stacktrace += g.errorCatcher.getFunctionName(func) + g.errorCatcher.getFunctionArgumentsString(func) + '\n';
    used.push(func);
    try {
      func = func.caller;
      for (var i = 0; i < used.length; i++) {
        if (used[i] == func) {
          stacktrace += g.errorCatcher.getFunctionName(func) + '(???)\n(...)\n';
          break stacktraceLoop;
        }
      }
    } catch(exception) {
      stacktrace += '(???' + exception.message + ')\n';
      break stacktraceLoop;
    }
    if (length > 50) {
      stacktrace += '(...)\n';
    }
  } while (func);
  return stacktrace;
};


/**
 * @param {string} string The string to shorten.
 * @param {number} maxLength The maximum length of the new string.
 * @return {string} The string, shortened if it exceeds maxLength.
 */
g.errorCatcher.shortenString = function(string, maxLength) {
  if (string.length > maxLength) {
    string = string.substr(0, maxLength) + '...';
  }
  return string;
};


/**
 * @param {Function} func The function to get the name of.
 * @return {string} The name of the function, or a snippet of the function's source code if it is an anonymous function.
 */
g.errorCatcher.getFunctionName = function(func) {
  var name;
  try {
    if ('name' in Function.prototype && func.name) {
      name = func.name;
    } else {
      var funcStr = func.toString();
      var matches = /function ([^\(]+)/.exec(funcStr);
      name = matches && matches[1] || '[anonymous function: ' + g.errorCatcher.shortenString(func.toString(), 90) + ']';
    }
  } catch(exception) {
    name = '[inaccessible function]'
  }
  return name;
};


/**
 * @param func The function to get a string describing the arguments for. Must be in the current callstack.
 * @return {string} A string of the arguments passed to the function.
 */
g.errorCatcher.getFunctionArgumentsString = function(func) {
  var argsStrings = [];
  try {
    var args = func.arguments;
    if (args) {
      for (var i = 0, length = args.length; i < length; i++) {
        argsStrings.push(g.errorCatcher.stringify(args[i]));
      }
    }
  } catch(exception) {
    argsStrings.push('...?');
  }
  return '(' + argsStrings.join(',') + ')';
};


/**
 * Converts objects and primitives to strings describing them. String inputs are redacted.
 * @param {*} thing The object or primitive to describe.
 * @return {string} String describing the input.
 */
g.errorCatcher.stringify = function(thing) {
  var string = '[???]';
  try {
    var type = typeof thing;
    string = '[' + type + '?]';
    switch (type) {
      case 'undefined':
          string = 'undefined';
          break;
      case 'number':
      case 'boolean':
          string = thing.toString();
          break;
      case 'object':
          if (thing == null) {
            string = 'null';
            break;
          }
          if (thing instanceof Date) {
            string = 'new Date("' + thing.toString() + '")';
            break;
          }
          var toStringValue = thing.toString();
          if (/^\[[a-z ]*\]$/i.test(toStringValue)) {
            string = toStringValue;
            break;
          }
          if (typeof thing.length == 'number') {
            string = '[arraylike object, length = ' + thing.length + ']';
            break;
          }
          string = '[object]';
          break;
      case 'string':
          string = '"' + g.errorCatcher.redactString(thing) + '"';
          break;
      case 'function':
          string = '/* function */ ' + g.errorCatcher.getFunctionName(thing);
          break;
      default:
          string = '[' + type + '???]';
          break;
    }
  } catch(exception) { }
  return string;
};


/**
 * Finds quoted strings in a Firefox stacktrace and replaces them with redacted versions. Handles pesky escaped quotes
 * too. This relies on Firefox's specific stringification/escaping behavior and might not work as consistently in other
 * browsers.
 * @param {string} stacktraceStr The stacktrace to redact strings from.
 * @return {string} The stacktrace, with strings redacted.
 */
g.errorCatcher.redactFirefoxStacktraceStrings = function(stacktraceStr) {
  if (!/\"/.test(stacktraceStr)) {
    return stacktraceStr;
  }
  // We can safely use new ecmascript array methods because this code only runs in Firefox.
  return stacktraceStr.split('\n').map(function(stacktraceLine) {
    var quoteLocations = [];
    var index = 0;
    do {
      index = (stacktraceLine.indexOf('"', index + 1));
      if (index != -1) {
        quoteLocations.push(index);
      }
    } while (index != -1);
    quoteLocations = quoteLocations.filter(function(quoteLocation) {
      var backslashCount = 0, index = quoteLocation;
      while (index--) {
        if (stacktraceLine.charAt(index) != '\\') {
          break;
        }
        backslashCount = backslashCount + 1;
      }
      // If a quotation mark is preceded by a non-even number of backslashes, it is escaped. Otherwise, only the
      // backslashes are escaped.
      // \"    escaped quote
      // \\"   escaped backslash, unescaped quote
      // \\\"  escaped backslash, escaped quote
      // (etc)
      return (backslashCount % 2 == 0);
    });
    if (quoteLocations.length % 2 == 1) {
      quoteLocations.push(stacktraceLine.length);
    }
    for (var i = quoteLocations.length - 1; i > 0; i -= 2) {
      stacktraceLine = stacktraceLine.substr(0, quoteLocations[i - 1] + 1) +
          g.errorCatcher.redactString(stacktraceLine.substring(quoteLocations[i - 1] + 1, quoteLocations[i])) +
          stacktraceLine.substr(quoteLocations[i]);
    }
    return stacktraceLine;
  }).join('\n');
};


/**
 * Redacts a string for user privacy.
 * @param {string} str The string to redact.
 * @return {string} The redacted string.
 */
g.errorCatcher.redactString = function(str) {
  return '[string redacted]';
  // This commented out alternative attempts to at least make certain types of string (HTML, for example) maintain a
  // recognizable pattern.
  // return g.errorCatcher.shortenString(str.replace(/[a-z]/g, 'x').replace(/[A-Z]/g, 'X').replace(/[0-9]/g, '#').replace(
  //    /[^\\\s\[\]<>xX\"\'\(\)\.\,\?\!\#\=\:\;\&\|\@\_\-]/g, '*'), 150).replace(/\r/g, '').replace(/\n/g, '\\n');
};


// g.errorCatcher can cause problems with debuggers (it breaks the Firebug console, for example), so it should be
// disabled in development environments. This if statements g.errorCatcher if you're using
if (!/[&?]nogec/.test(location.href)) {
  g.errorCatcher(function(errorObj) {
    jQuery.ajax({
      url: '/gec_js',
      data: errorObj,
      type:'POST'
    });
  }, function(str) {
  // this is the URL redaction function. this one just removes ?q= paramter values, but you should adapt this to your
  // own application if needed.
  return str.replace(/([\#\?\&][Qq]\=)[^\=\&\#\s]*/g, '$1[redacted]');
  });
}
