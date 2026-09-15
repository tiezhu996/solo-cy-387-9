"""用户行级串行边界。

所有会改变待办归属或账号启用状态的写事务，都先在用户行上加锁，使「领取待办」
「停用账号」「接管给他人」在同一把行锁上串行化，避免交错后待办挂在已停用
账号名下。多账号事务必须按用户 id 升序加锁（见 lock_users_ordered），防止死锁。

实现为「无变化 UPDATE」：
- PostgreSQL：UPDATE 对命中行加排他行锁，READ COMMITTED 下拿到锁后以行最新
  版本重新评估 WHERE 条件，即提交前重新确认启用状态；
- SQLite：UPDATE 是写语句，使事务立即进入写状态（整个库写事务互斥），同时
  避免「先读后写」的快照锁升级错误。
"""

from django.db.models import F

from app.constants.errors import BusinessError
from .models import User


def lock_user(user_id) -> User:
    """无条件锁定用户行（固定加锁顺序用），返回锁内最新用户；不存在则 404。"""
    matched = User.objects.filter(pk=user_id).update(is_active=F('is_active'))
    if not matched:
        raise BusinessError('USER_NOT_FOUND', 404)
    return User.objects.get(pk=user_id)


def lock_users_ordered(user_ids) -> None:
    """按 id 升序依次锁定多个用户行，保证多账号事务加锁顺序全局一致。"""
    for uid in sorted(set(int(x) for x in user_ids if x is not None)):
        lock_user(uid)


def lock_active_user(user_id) -> User:
    """锁定用户行并确认其仍启用；停用/不存在则抛业务异常（调用方事务回滚）。"""
    user = lock_user(user_id)
    if not user.is_active:
        raise BusinessError('USER_DISABLED', 403, '账号已停用或正被停用，无法领取待办')
    return user


def lock_active_target(user_id, code='TAKEOVER_TARGET_DISABLED',
                       message='接管人已被停用或正被停用，请更换接管人或退回公共池') -> User:
    """锁定接管目标行并确认仍启用；否则整笔交接失败、整体回滚。"""
    user = lock_user(user_id)
    if not user.is_active:
        raise BusinessError(code, 409, message)
    return user
