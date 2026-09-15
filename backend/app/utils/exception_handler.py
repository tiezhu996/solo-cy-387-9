from rest_framework.views import exception_handler

def standard_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response
    response.data = {'success': False, 'code': response.status_code, 'data': None, 'error': response.data}
    return response
