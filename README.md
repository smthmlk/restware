restware
========

Restware is a plugin and a piece of middleware designed to make Bottle (bottlepy.org) easier to use to build REST APIs in Python. It specifically targets a few common guidelines for REST APIs and handles them for you: JSON in/out, always (even for error responses); Pretty-print JSON via query arg; Gzip in/out, always (if the client sends/can accept gzipped data). 
