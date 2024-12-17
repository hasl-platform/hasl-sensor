class SLAPI_Error(Exception):
    """Base class for SL exceptions."""
    def __init__(self, code, message, details=None):
        self._code = code
        self._message = message
        self._details = details

    def __str__(self):
        return "SLAPI_Error {0}: {1}".format(self._code, self._message)

    @property
    def details(self):
        return self._details

    @property
    def message(self):
        return self._message

    @property
    def code(self):
        return self._code


class SLAPI_API_Error(SLAPI_Error):
    """An API-level exception occurred."""
    def __str__(self):
        return "SLAPI_API_Error {0}: {1}".format(self._code, self._message)


class SLAPI_HTTP_Error(SLAPI_Error):
    """An HTTP-level exception occurred."""
    def __str__(self):
        return "SLAPI_HTTP_Error {0}: {1}".format(self._code, self._message)
