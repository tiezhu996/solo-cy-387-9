"""现场照片上传：保存到 MEDIA_ROOT/uploads，返回可访问 URL。"""

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from app.constants.errors import BusinessError
from app.utils.permissions import ActiveUserPermission
from app.utils.response import ok

ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'}


class PhotoUploadView(APIView):
    permission_classes = [ActiveUserPermission]
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if upload is None:
            raise BusinessError('VALIDATION_ERROR', 400, '请选择要上传的照片')
        ext = '.' + upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else '.jpg'
        if ext not in ALLOWED_EXT:
            raise BusinessError('VALIDATION_ERROR', 400, '仅支持 jpg/png/gif/webp 格式')
        if upload.size > 10 * 1024 * 1024:
            raise BusinessError('VALIDATION_ERROR', 400, '照片不能超过 10MB')
        name = f'{uuid.uuid4().hex}{ext}'
        path = settings.MEDIA_ROOT / 'uploads' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(upload.read())
        return ok({'url': f'{settings.MEDIA_URL}uploads/{name}', 'name': upload.name}, 201)
