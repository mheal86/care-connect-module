"""HTTP error contract required by the exported module."""
from fastapi import HTTPException
from fastapi.responses import JSONResponse

class CodedHTTPException(HTTPException):
    def __init__(self, status_code, code, detail, params=None, headers=None):
        super().__init__(status_code, detail, headers)
        self.code = code
        self.params = dict(params or {})

async def coded_http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code,
        content={'detail': exc.detail, 'code': exc.code, 'params': exc.params}, headers=exc.headers)

def install_error_handlers(app):
    app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)
