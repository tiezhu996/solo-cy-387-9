from app.utils.logger import get_logger

logger = get_logger('request')

class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info('%s %s', request.method, request.path)
        return self.get_response(request)
