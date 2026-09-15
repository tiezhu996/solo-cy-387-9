"""DRF 统一异常处理：所有响应保持 {success, code, data, error} 标准结构。"""

from rest_framework.views import exception_handler as drf_exception_handler

from app.constants.errors import BusinessError
from app.utils.logger import get_logger

logger = get_logger('exception')


def standard_exception_handler(exc, context):
    # 业务异常转换为标准 JSON 响应
    if isinstance(exc, BusinessError):
        from rest_framework.response import Response
        logger.info('业务异常: %s %s', exc.code, exc.message)
        return Response(
            {'success': False, 'code': exc.code, 'data': None, 'error': exc.message},
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception('未处理异常')
        from rest_framework.response import Response
        return Response(
            {'success': False, 'code': 'INTERNAL_ERROR', 'data': None, 'error': '服务器内部错误'},
            status=500,
        )

    # DRF 校验/权限等异常，摊平错误信息
    detail = response.data
    if isinstance(detail, dict):
        if 'detail' in detail:
            error = str(detail['detail'])
        else:
            first = next(iter(detail.values()), detail)
            error = first[0] if isinstance(first, list) and first else str(detail)
            error = str(error)
    else:
        error = str(detail)
    response.data = {'success': False, 'code': 'API_ERROR', 'data': None, 'error': error}
    return response
