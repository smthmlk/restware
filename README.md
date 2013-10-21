restware
========

Restware is a plugin and a piece of middleware designed to make Bottle (bottlepy.org) easier to use to build REST APIs in Python. It specifically targets a few common guidelines for REST APIs and handles them for you (JSON in/out, Gzipping in/out, pretty-printing JSON) 

Features
--------
* JSON input (request body) and output (response body)
    * Anything in the request.body is deserialized from JSON if the request.headers['Content-Type'] has "application/json" in it. Bottle does this for you, but it's got a memory limit of 102400 bytes, which it kind of silently imposes on you. We work around that.
    * Anything in the response.body is serialized to JSON
        * This is configurable so that only routes under a base-path have their response data serialized as JSON
* JSON response pretty-printing 
    * All responses can be pretty-printed automatically if the user adds the _pretty_ query parameter with value _true_. By default, all responses come back with the most compact JSON representation possible
* Transparent Gzip handling for input (request body) and output (response body)
    * Your app does not need to worry about receving a POST with a gzipped request body: it is handled by the Restware middleware
    * Your app's responses--JSON or not--will be gzipped if the client can handle it (request _Accept-Encoding_ header must include _gzip_) otherwise the content is sent uncompressed

Python, Bottle Versions
-----------------------
This is known to work with Python 2.[67], and Bottle >= 0.11

Example Usage
-------------
See the included example_app.py which is a fully functional REST api that uses restware.

Here's what you need to do to help turn bottle into a better platform for writing a REST API

```python
import bottle
import restware

# Get bottle's default app
app = bottle.app()

# define the routes for your bottle app here.
# ...

# Install the RestwarePlugin into the app
# All of our API operations will reside under /api/, so this plugin will only do its JSON magic
# for routes under that base-path
app.install(restware.RestwarePlugin(baseRulePath="/api/"))

# Wrap the app with our Restware middleware
wrapped_app = restware.Restware(app)

# Start the webserver. We'll use CherryPy
bottle.run(app=wrapped_app, host="0.0.0.0", port=8080, debug=True, server='cherrypy')
```

And that's it. Notice that we are using server='cherrypy'; this is because Bottle's reference WSGI server is really inferior, and cherrypy lets you add stuff like SSL (another REST API guideline recommendation) really easily to any bottle app.


Serving JSON and non-JSON from the same App
-------------------------------------------
I like to provide at least basic usage documentation from the API itself, and to keep things simple, I wanted the same bottle app to serve both the documentation and the API operations. Documentation for humans to read is likely something Sphinx generated, and not JSON, so the RestwarePlugin needs to be able to not enforce JSON-only responses all the time.

The RestwarePlugin has a constructor parameter "baseApiPath" that defines what routes it tries to send JSON responses for. This lets you serve your documentation under the root page (/) or a specific sub-directory (/docs) and you won't have JSON returned to clients, while things under, say, apiBasePath='/api/' (the default) will cause all routes under /api/.* to return JSON to clients.

```python
import restware
import bottle

# Set the apiBasePath so only our API calls get returned as JSON, while 
# /help will not be tampered with
app = bottle.app()
app.install(restware.RestwarePlugin(apiBasePath="/api/")

# This will return HTML, something that doesn't make sense to return in JSON
@app.get("/help")
def help():
   return static_file(filename="help.html", root=".")

# This will return a dict, something that does make sense to return in JSON
@app.get("/api/v1/cardboard-box/<boxId>")
def getBoxById(boxId):
   # ...
   return {"boxId": boxId, "otherKeys":"..."}

# Wrap with our middleware & run the app
wrapped_app = restware.Restware(app)
bottle.run(app=wrapped_app, ...)
```

Logging
-------
The plugin and middleware both take optional logging.Logger instances in their constructors. If you don't provide one, they make their own and default to level DEBUG, which is probably more verbose than you want after you've got things working.

Here's how to quickly setup a logger the just spits things out to stdout:
```python
import logging
import restware
import sys

logger = logging.getLogger("my customized logger")
handler = logging.StreamHandler(sys.stdout)
# The format string is up to you; this is what I use for simple projects
handler.setFormatter(logging.Formatter("%(levelname)s %(module)s:%(funcName)s %(asctime)s | %(message)s"))
logger.addHandler(handler)
# You probably want the INFO level..
logger.setLevel(logging.INFO)

# Use this logger with the plugin & middleware
pluginInst = restware.RestwarePlugin(logger=logger)
wrapped_app = restware.Restware(logger=logger, app=...)
```
