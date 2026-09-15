"""用户行级串行边界。

领取待办与停用账号必须落在同一把行锁上串行化，避免「领取写入」与「停用交接」
交错后，待办最终挂在已停用账号名下。

实现为一次「无变化 UPDATE」：
- PostgreSQL：UPDATE 会对命中的用户行加排他行锁，并在 READ COMMITTED 下于
  拿到锁后以该行最新版本重新评估 is_active 条件——即提交前重新确认仍启用；
- SQLite：UPDATE 是写语句，使事务立即进入写状态（整个库写事务互斥），
  同时避免「先读后写」的快照锁升级错误。

调用方必须把它作为写事务内的第一条数据库语句。
"""

from django.db.models import F

from app.constants.errors import BusinessError
from .models import User


def lock_active_user(user_id) -> None:
    """锁定用户行并确认其仍启用；停用/不存在则抛业务异常（调用方事务回滚）。"""
    matched = User.objects.filter(pk=user_id, is_active=True).update(is_active=F('is_active'))
    if matched:
        return
    if User.objects.filter(pk=user_id).exists():
        raise BusinessError('USER_DISABLED', 403, '账号已停用或正被停用，无法领取待办')
    raise BusinessError('USER_NOT_FOUND', 404)
