"""统一成功响应结构。"""

from rest_framework.response import Response


def ok(data=None, status_code: int = 200) -> Response:
    return Response({'success': True, 'code': 'OK', 'data': data, 'error': None}, status=status_code)
