greplin-exception-catcher
=====================

Greplin Exception Catcher (GEC)
----------------------------

Exception collection and aggregation built on Google App Engine.


### Why:

The ability to see aggregated exception logs in (near) real time is invaluable for determining how your application is
performing.


### Demonstration:

Here is a [demo server](http://gecdemo.appspot.com) running the exception catcher.

[Click here](http:/gecdemo.appspot.com/error) to trigger 10 more fake exceptions.

The demo server generates fake exceptions using [this fork](http://github.com/robbywalker/greplin-exception-catcher).


### Why App Engine:

App Engine gave us a lot of what we needed for free (task queues, persistent storage, etc) plus it makes it very easy
for other companies to deploy this code base.


### Status:

This is a very early stage project.  It works for our needs.  We haven't verified it works beyond that.  Issue reports
and patches are very much appreciated!

For example, some obviously needed improvements include

* Faster data store access, particularly for large data sets.

* Email on error spikes.

* Over time graphs of specific errors.

* Integration with more languages / frameworks.

* The visual design could use a lot of love.


### Pre-requisites:

[App Engine](http://code.google.com/appengine/)


### Installation

    git clone https://github.com/Greplin/greplin-exception-catcher.git


### Installation (server):

    cd greplin-exception-catcher/server

    cp example-config.json config.json

At this point, update config.json with the name and secret key.  Secret key should be any random string of characters.

    dev_appserver.py .

#### Notes on deploying to App Engine

You'll need to change the application identifier in app.yaml to an identifier that you own.

GEC currently requires that you attach it to a single Google Apps domain for login security.


### Python using built-in logging

#### Installation

    cd greplin-exception-catcher/python/logging

    python setup.py install


#### Usage

    import logging
    from greplin.gec import logHandler

    gec = logHandler.GecHandler('/path/to/exception/directory', projectName, environmentName, serverName)
    gec.setLevel(logging.ERROR)
    logging.getLogger().addHandler(gec)



### Python using Twisted

#### Installation

    cd greplin-exception-catcher/python/twisted

    python setup.py install

#### Usage

    from greplin.gec import twistedLog
    twistedLog.GecLogObserver('/path/to/exception/directory', projectName, environmentName, serverName).start()


### Java using log4j

#### Installation

    cd greplin-exception-catcher/java

    mvn install

#### Usage

In log4j.properties:

    log4j.appender.gec=com.greplin.gec.GecAppender
    log4j.appender.gec.project=Project name
    log4j.appender.gec.outputDirectory=/path/to/exception/directory
    log4j.appender.gec.environment=prod/devel/etc.
    log4j.appender.gec.serverName=Server name


### Cron installation

Add the following to your crontab:

    * * * * * /path/to/greplin-exception-catcher/bin/upload.py http://your.server.com YOUR_SECRET_KEY /path/to/exception/directory


### Design highlights:

When exceptions occur, they are written to a directory of individual JSON files.  A cron job must be set up
to scan this directory for new exceptions and send them to the App Engine server.

We chose this model so that exception logging will be resilient to transient server side problems.


### Authors:

[Greplin, Inc.](http://www.greplin.com)
