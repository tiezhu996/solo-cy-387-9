"""状态历史记录辅助：所有状态流转统一从这里留痕，保证记录不丢失。"""

from app.apps.audit.models import StatusHistory


def record_history(target_type, target_id, action, from_status='', to_status='',
                   actor=None, detail=''):
    return StatusHistory.objects.create(
        target_type=target_type,
        target_id=target_id,
        action=action,
        from_status=from_status or '',
        to_status=to_status or '',
        actor=actor if (actor and actor.is_authenticated) else None,
        actor_name=getattr(actor, 'name', '') if actor else '',
        detail=detail or '',
    )
