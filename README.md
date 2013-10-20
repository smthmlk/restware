restware
========

Restware is a plugin and a piece of middleware designed to make Bottle (bottlepy.org) easier to use to build REST APIs in Python. It specifically targets a few common guidelines for REST APIs and handles them for you: 
* JSON in/out, always (even for error responses)
* Pretty-print JSON via query arg
* Gzip in/out, always (if the client sends/can accept gzipped data)

Example Usage
-------------
See the included example_app.py which is a fully functional REST api that uses restware.

Here's what you need to do to help turn bottle into a better platform for writing a REST API

```python
import bottle
from bottle import get, put, delete
import restware

# Get bottle's default app
app = bottle.app()

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


