import StringIO
import gzip
import json
import logging
import sys

import bottle
from bottle import response, request

class RestwarePlugin:
    """
    This plugin is designed to fix a few peculiar behaviors that keep Bottle from being a really
    good engine for quickly developing a REST-esque API.

    The two issues rectified by this module are:
        1. Errors (400+ status code responses) are now always JSON responses
        2. All request body data is checked for JSON in case the memory limit imposed by bottle
           comes into play; all response body data are automatically treated as JSON if they can
           be treated that way

    You can configure just one thing: what route prefix should be handled as JSON for response
    body data. This lets your app serve up documentation (static HTML, likely) while a set of
    routes that make up your API's operations are all treated as if they're going to return JSON
    """
    name = "restwareplugin"
    api = 2

    def __init__(self, baseRulePath='/api/', logger=None):
        self.baseRulePath = baseRulePath
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger("RestPlugin")
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(levelname)s %(module)s:%(funcName)s | %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def setup(self, app):
        '''
        Set all error status codes so that our own error handler function is used. We'll also go ahead
        and wrap that function with our Gzip and JSON'ing method (apply()). This way we get uniform behavior
        from our app, even when errors are returned: the client will never see HTML, only text or JSON.
        '''
        def standardErrorHandlerFunc(errorInst):
            self.logger.warn("error, %s" % errorInst.status)
            if type(errorInst.body) is not dict:
                return {"message":errorInst.body}
            return errorInst.body

        for errorCode in [statusCode for statusCode, description in bottle.HTTP_CODES.iteritems() if statusCode >= 400]:
            self.logger.debug("applying for status-code %d" % errorCode)
            app.error_handler[int(errorCode)] = self.apply(standardErrorHandlerFunc, "error")

    def apply(self, callback, route):
        '''
        This method wraps the given callback function so that we can try to serialize the response data
        as JSON, and then Gzip the returned string. This only applies in two scenarios:
            for routes whose rule starts with "/api/"
            for errors (400+)

        This only applies when the data returned from the callback if of type list or dict. If it is something
        else, then we let bottle do whatever it would normally do. Other data will be returned, but a warning
        message is printed to stdout if a /api/* route returns something we aren't able to serialize as JSON.

        We can also return pretty-printed JSON. All the client must do is specify the "pretty" query parameter
        and give it the "true" value: &pretty=true
        '''
        '''
        if route == "error":
            # Apply to all error responses, no exceptions
            self.logger.debug("applying REST wrapper for Error callback %s" % repr(callback))
        #elif route is not None and hasattr(route, 'rule') and route.rule.startswith(self.baseRulePath):
        #    self.logger.debug("applying REST wrapper to API callback=%s, rule=%s" % (repr(callback), route.rule))
        else:
            # do not apply.
            self.logger.debug("not applying REST wrapper to callback=%s: rule not under %s, and not an error route" % (repr(callback), self.baseRulePath))
            return callback
        '''
        def wrapper(*args, **kwargs):
            # perform pre operations to setup the request if necessary
            #self.preprocessRequest(route)
            retval = callback(*args, **kwargs)
            return self.postprocessRequest(retval, route)
        return wrapper

    def preprocessRequest(self, route):
        """
        This preprocessor specifically looks for POSTed JSON that exceeds bottle's MEMLIMIT (102400 bytes I think)
        """
        if not request.headers.get("Content-Type","").startswith("application/json"):
            # there is no JSON posted, so we can return
            self.logger.debug("No JSON to decode; finished")
            return

        # JSON is expected, so ensure it is either already parsed by bottle, or parse it ourselves
        if hasattr(request, "json") and request.json is not None:
            # It is already parsed, so there's nothing to do
            self.logger.debug("JSON data already parsed by bottle")
            return
        else:
            self.logger.warn("Attempting to parse JSON from request.body since request.json is missing/None")
            # ensure some data was actually POSTed
            if hasattr(request, "body") and request.body:
                try:
                    # TODO: set encoding based on request header
                    request.json = json.load(request.body)
                    self.logger.debug("Decoded %d bytes of JSON successfully" % len(request.body))
                except Exception, e:
                    self.logger.warn("Request header Content-Type indicates JSON, and we failed to parse request.body: %s" % e)
                    request.body.seek(0)
                    print "data=%s" % repr(request.body.read())
                    request.json = None
            else:
                self.logger.warn("Request header Content-Type indicates JSON, but no data was POSTed?")
                request.json = None

    def postprocessRequest(self, retval, route):
        """
        Ensures the output is JSON. That's all this method does.
        """
        JSONed = False
        GZIPPED = False

        # Is this request under the a path we're enforcing JSON output for?
        if (route is not None and hasattr(route, 'rule') and route.rule.startswith(self.baseRulePath)) or response.status_code >= 400:
            # It is. Try to serialize the returned data as JSON
            self.logger.debug("response should be JSON")

            # First, is the data even something we can serialize as JSON?
            # if the retval is not a dict, we don't know what to do with it, so just be transparent
            if type(retval) not in (dict, list):
                self.logger.error("\033[41;1m You are trying to send the client data that doesn't look like it should be JSON (%s). Fix this! \033[0m" % type(retval))
            else:
                # Was the "pretty" query parameter set?
                if request.query.get("pretty") == 'true':
                    # It was. Indent & sort keys
                    self.logger.debug("found pretty query param, value is true, prettying JSON")
                    retval = json.dumps(retval, indent=4, sort_keys=True)
                else:
                    # It was not. By default, we'll use the most compact representation
                    retval = json.dumps(retval, separators=(',',':'))
                response.content_type = "application/json"
                self.logger.debug("%d bytes of JSON created" % len(retval))
                JSONed = True
        else:
            self.logger.debug("response should NOT be JSON")

        # Gzipping the response
        # Can the client even handle gzipped response bodies?
        if 'gzip' in request.headers.get("Accept-Encoding","") and len(retval) > 0:
            self.logger.debug("client accepts gzip, gzipping data")
            # the client handle gzipped data, so lets gzip out data
            self.logger.debug("original response data was %d bytes" % len(retval))
            sio = StringIO.StringIO()
            gzFile = gzip.GzipFile(fileobj=sio, mode='wb', compresslevel=6)
            gzFile.write(retval)
            gzFile.close()
            sio.seek(0)
            retval = sio.read()
            sio.close()

            # update the content-length (it is already set) and add the content-encoding header
            response.set_header('Content-Length',str(len(retval)))
            response.set_header('Content-Encoding','gzip')
            self.logger.debug("new gzipped response data is %d bytes" % len(retval))
            GZIPPED = True
        else:
            self.logger.debug("client either doesn't accept gzip or there's no data to return")

        self.logger.info("RESPONSE %s gzipped:%s json:%s size:%dB" % (response.status_code, GZIPPED, JSONed, len(retval)))
        return retval


class Restware(object):
    """
    Middleware that handles gzipping incoming and outgoing data. This should work with any other WSGI app obviously,
    but it is tested with Bottle.

    As stated, this middlware approach fixes the other big issue with Bottle (and some other WSGI frameworks) which
    do not handle gzipping content. For example:
        * this class will seamlessly handle POSTed data which is gzipped or not gzipped; if it is gzipped, it will
          decompress it, update the Content-Length request header, and the wrapped app will not have to deal with
          gzipped data
        * Similarly, this class will seamlessly gzip response data and update/add response headers as necessary if
          the client's request header "Accept-Encoding" includes gzip; if it doesn't, then the data is not
          compressed

    Combining this middleware and the plugin for bottle will yield a great place to start for building a quick,
    guideline-following RESTful API using Bottle.
    """
    def __init__(self, app, apiBasePath='/', logger=None):
        self.app = app
        self.apiBasePath = apiBasePath
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger("Restware")
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(levelname)s %(module)s:%(funcName)s %(asctime)s| %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def postprocess(self, yieldedData, environ):
        # We can now post-process whatever the app we're wrapping is sending back to the client
        if 'gzip' in environ.get("HTTP_ACCEPT_ENCODING","") and len(yieldedData) > 0:
            self.logger.debug("client accepts gzip, gzipping data")
            # the client handle gzipped data, so lets gzip out data
            self.logger.debug("original response data was %d bytes" % len(yieldedData))
            sio = StringIO.StringIO()
            gzFile = gzip.GzipFile(fileobj=sio, mode='wb', compresslevel=6)
            gzFile.write(yieldedData)
            gzFile.close()
            sio.seek(0)
            yieldedData = sio.read()
            sio.close()

            # update the content-length (it is already set) and add the content-encoding header
            print "restware.postprocess(): headers=>%x" % id(self.headers)
            for idx, header in enumerate(self.headers):
                if header[0].lower() in ('content-length', 'content-encoding'):
                    self.headers.pop(idx)
                    self.logger.debug("found existing response header %s; removing" % header[0])
            self.headers.append(('Content-Length',len(yieldedData)))
            self.headers.append(('Content-Encoding','gzip'))
            self.logger.debug("new gzipped response data is %d bytes" % len(yieldedData))
        else:
            self.logger.debug("client either doesn't accept gzip or there's no data to return")

        return yieldedData

    def preprocess(self, environ):
        # log a bit about this request.
        self.logger.info("REQUEST %(REQUEST_METHOD)s server=%(SERVER_NAME)s:%(SERVER_PORT)s path=%(PATH_INFO)s query=%(QUERY_STRING)s" % environ)

        # is this a POST, and if so, did they send along gzipped data?
        if environ['REQUEST_METHOD'] == 'POST' and environ.get("HTTP_CONTENT_ENCODING") == 'gzip':
            # we need to decompress the gzipped data
            self.logger.debug("gzipped data found in POST body")
            contentLength = int(environ.get('CONTENT_LENGTH',0))
            compressedData = environ['wsgi.input'].read(contentLength)
            sio = StringIO.StringIO(compressedData)
            gzFile = gzip.GzipFile(fileobj=sio)
            decompressedData = gzFile.read()
            gzFile.close()
            sio.close()
            environ['wsgi.input'] = StringIO.StringIO(decompressedData)
            environ['CONTENT_LENGTH'] = str(len(decompressedData))
            self.logger.debug("expanded %d bytes of gzip into %d bytes of uncompressed data" % (contentLength, len(decompressedData)))

    def __call__(self, environ, start_response):
        self.preprocess(environ)

        # This is ugly as hell.
        # WSGI does not let us have access to the response headers unless we call start_response and provide some...
        # but we're middleware. Someone else before us is going to call that. We want to modify the headers they specify, or add to them
        # So the ugly hack is to wrap the start_response func so that we can get a reference to the headers list. Once we get a ref,
        # we keep it in self, so that we may have it in scope for post-processing the wrapped app's response.
        self.headers = None
        def custom_start_response(status, headers, exc_info=None):
            print "restware.custom_start_process(): headers=>%x" % id(headers)
            self.headers = headers
            return start_response(status, self.headers, exc_info)

        return self.app(environ, start_response)
        #for i in self.app(environ, custom_start_response):
        #    yield self.postprocess(i, environ)

