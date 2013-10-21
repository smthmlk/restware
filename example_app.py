import bottle
from bottle import get, put, delete
import restware

# Holds the data for function that this example API is trying to implement for some one
keyStoreD = {}

@get("/")
def root():
    # Returns some documentation for the user to look at
    # Consider using Sphinx and sphinxcontrib-httpdomain .. but this is just an example
    return  """
            <header><h1>Example API app Documentation</h1>
            <h2>GET /api/v1/key/(str:keyName)</h2>Returns the value for the given key.
            <h2>PUT /api/v1/key/(str:keyName)/value/(str:value)</h2>Store a value for a key.
            <h2>DELETE /api/v1/key/(str:keyName)</h2>Delete a key and its value from the store
            </body></html>
            """

# The following three routes make up our actual example API
@get("/api/v1/key/<keyName>")
def getKey(keyName):
    return {keyName:keyStoreD.get(keyName, None)}

@put("/api/v1/key/<keyName>/value/<value>")
def storeKeyValue(keyName, value):
    try:
        keyStoreD[keyName] = value
    except Exception, e:
        return {"error":"failed to store value for key: %s" % e}
    return {keyName:value}

@delete("/api/v1/key/<keyName>")
def deleteKey(keyName):
    if keyName in keyStoreD:
        del keyStoreD[keyName]
        return {keyName:None}
    return {"error":"no such key; cannot delete"}

# DEPLOYMENT TIME
# Get bottle's default app
app = bottle.app()

# Install the RestwarePlugin into the app
# All of our API operations will reside under /api/, so this plugin will only do its JSON magic for routes under that base-path
app.install(restware.RestwarePlugin(apiBasePath="/api/"))

# Wrap the app with our Restware middleware
wrapped_app = restware.Restware(app)

# Start the webserver. We'll use CherryPy
bottle.run(app=wrapped_app, host="0.0.0.0", port=8080, debug=True, server='cherrypy')
