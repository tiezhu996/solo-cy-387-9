"""初始化演示数据：账号、楼栋区域、若干不同状态的巡检任务与整改单。

    python manage.py bootstrap_demo
幂等：已有数据时直接跳过。
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.apps.organization.models import Area, Building
from app.apps.users.models import User
from app.apps.inspection.models import InspectionTask
from app.apps.inspection.services import publish_task, claim_task, submit_inspection
from app.apps.rectification.services import claim_order, submit_resolution

PASSWORD = 'demo123456'

ACCOUNTS = [
    ('wuye', '王物业', 'property'),
    ('xunjian1', '李巡检', 'inspector'),
    ('xunjian2', '赵巡检', 'inspector'),
    ('zhenggai1', '钱整改', 'rectifier'),
    ('zhenggai2', '孙整改', 'rectifier'),
    ('zhuguan', '周主管', 'supervisor'),
]


class Command(BaseCommand):
    help = '初始化演示数据（幂等）'

    def handle(self, *args, **options):
        if User.objects.filter(username='wuye').exists():
            self.stdout.write('演示数据已存在，跳过')
            return

        users = {}
        for username, name, role in ACCOUNTS:
            users[username] = User.objects.create_user(
                username=username, password=PASSWORD, name=name, role=role,
                phone='13800000000',
            )

        a_building = Building.objects.create(code='A', name='A栋住宅楼')
        b_building = Building.objects.create(code='B', name='B栋住宅楼')
        area_lobby = Area.objects.create(building=a_building, code='LOBBY', name='一层大堂', location='A栋一层')
        area_garage = Area.objects.create(building=a_building, code='GARAGE', name='地下车库B2', location='A栋B2层')
        area_corridor = Area.objects.create(building=b_building, code='CORRIDOR', name='三层走廊', location='B栋三层')
        checklist = ['消防通道是否畅通', '应急照明是否正常', '地面是否有积水', '垃圾是否日清']

        now = timezone.now()
        manager = users['wuye']

        # 1) 待领取任务（公共池）
        publish_task(
            title='A栋一层大堂日巡检', building_id=a_building.id, area_id=area_lobby.id,
            period='daily', scheduled_at=now + timedelta(hours=1), due_at=now + timedelta(days=1),
            checklist=checklist, publisher=manager,
        )

        # 2) 已被李巡检领取、巡检中的任务
        task2 = publish_task(
            title='B栋三层走廊日巡检', building_id=b_building.id, area_id=area_corridor.id,
            period='daily', scheduled_at=now - timedelta(hours=2), due_at=now + timedelta(days=1),
            checklist=checklist, publisher=manager,
        )
        claim_task(task2.id, users['xunjian1'])

        # 3) 提交了异常、已生成整改单，整改单待领取
        task3 = publish_task(
            title='A栋地下车库周巡检', building_id=a_building.id, area_id=area_garage.id,
            period='weekly', scheduled_at=now - timedelta(days=1), due_at=now + timedelta(days=2),
            checklist=checklist, publisher=manager,
        )
        claim_task(task3.id, users['xunjian1'])
        submit_inspection(task3.id, users['xunjian1'], [
            {'name': '消防通道是否畅通', 'result': 'issue',
             'description': 'B2层消防通道被废弃家具占用约2米宽', 'photos': []},
            {'name': '应急照明是否正常', 'result': 'normal', 'description': '', 'photos': []},
            {'name': '地面是否有积水', 'result': 'issue',
             'description': '3号车位上方管道滴漏，地面积水约3平米', 'photos': []},
            {'name': '垃圾是否日清', 'result': 'normal', 'description': '', 'photos': []},
        ], summary='车库两处问题需整改')

        # 4) 整改单已领取并提交结果，等待巡检员复验
        pending_order = task3.rectification_orders.order_by('id').first()
        claim_order(pending_order.id, users['zhenggai1'])
        submit_resolution(pending_order.id, users['zhenggai1'], '已联系清运废弃家具，通道恢复畅通', [])

        # 5) 一条全部正常、已关闭的历史任务，体现完整闭环
        task5 = publish_task(
            title='A栋大堂日巡检（历史）', building_id=a_building.id, area_id=area_lobby.id,
            period='daily', scheduled_at=now - timedelta(days=2), due_at=now - timedelta(days=1),
            checklist=checklist, publisher=manager,
        )
        claim_task(task5.id, users['xunjian2'])
        submit_inspection(task5.id, users['xunjian2'], [
            {'name': c, 'result': 'normal', 'description': '', 'photos': []} for c in checklist
        ])

        # 6) 一条已超期未领取任务（供超期升级扫描演示）
        publish_task(
            title='B栋走廊超期巡检（演示升级）', building_id=b_building.id, area_id=area_corridor.id,
            period='weekly', scheduled_at=now - timedelta(days=5), due_at=now - timedelta(days=3),
            checklist=checklist, publisher=manager,
        )

        self.stdout.write(self.style.SUCCESS('演示数据初始化完成'))
        self.stdout.write(f'演示账号密码统一为：{PASSWORD}')
