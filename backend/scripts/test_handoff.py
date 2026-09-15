# -*- coding: utf-8 -*-
"""停用交接专项验证：退回公共池 / 指定接管 / 并发停用-领取 / 历史保留 / 重新启用不拿回。"""
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "http://127.0.0.1:19407/api"
results = []


def call(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Token {token}')
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(name, cond, detail=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL '), name, '' if cond else f':: {detail}')
    return bool(cond)


def login(u):
    c, d = call('POST', '/auth/login/', body={'username': u, 'password': 'demo123456'})
    assert c == 200, d
    return d['data']['token']


P = login('wuye'); I1 = login('xunjian1'); I2 = login('xunjian2')
R1 = login('zhenggai1'); R2 = login('zhenggai2')

# 工具：物业发布并指派任务
_, buildings = call('GET', '/buildings/', P)
bid = buildings['data'][0]['id']
_, areas = call('GET', f'/areas/?building={bid}', P)
aid = areas['data'][0]['id']
now = datetime.now(timezone.utc)


def publish(assignee_token=None, title='停用交接任务'):
    uid = None
    if assignee_token:
        _, me = call('GET', '/auth/me/', assignee_token)
        uid = me['data']['id']
    c, d = call('POST', '/tasks/', P, {
        'title': title, 'building_id': bid, 'area_id': aid, 'period': 'daily',
        'scheduled_at': (now + timedelta(hours=1)).isoformat(),
        'due_at': (now + timedelta(days=2)).isoformat(),
        'checklist': ['消防', '照明'], 'assignee_id': uid,
    })
    assert c == 201, d
    return d['data']['id']


# ================================================== 1. 停用巡检员 → 在办任务退回公共池
tid = publish(I1, '巡检员停用-任务退池')
_, t = call('GET', f'/tasks/{tid}/', I1)
check('任务已归属李巡检且巡检中', t['data']['assignee_name'] == '李巡检' and t['data']['status'] == 'claimed', t['data'])
# 停用李巡检，不指定接管人
c, d = call('POST', '/users/2/active/', P, {'is_active': False})
check('停用成功并返回交接统计', c == 200 and d['data']['handoff']['task_count'] >= 1 and d['data']['handoff']['takeover'] is None, d)
_, t = call('GET', f'/tasks/{tid}/', I2)
check('任务退回公共池且待领取', t['data']['assignee_name'] is None and t['data']['status'] == 'pending', t['data'])
# 赵巡检可领取
c, d = call('POST', f'/tasks/{tid}/claim/', I2)
check('他人可领取被释放任务', c == 200 and d['data']['assignee_name'] == '赵巡检', d)
# 李巡检无法登录
c, d = call('POST', '/auth/login/', body={'username': 'xunjian1', 'password': 'demo123456'})
check('停用巡检员无法登录', c == 403 and d['code'] == 'USER_DISABLED', d)
# 历史仍可回查（包含李巡检领取、停用退池）
_, tl = call('GET', f'/tasks/{tid}/timeline/', I2)
actions = [e['action'] for e in tl['data']]
check('状态历史保留领取与退池记录', 'claim' in actions and 'handoff_pool' in actions, actions)
actors = [e['actor_name'] for e in tl['data']]
check('退池记录由物业操作留痕', any(e['action'] == 'handoff_pool' and e['actor_name'] == '王物业' for e in tl['data']), actors)

# 重新启用李巡检，不自动拿回
c, d = call('POST', '/users/2/active/', P, {'is_active': True})
check('重新启用成功', c == 200 and d['data']['is_active'] is True, d)
_, t = call('GET', f'/tasks/{tid}/', I2)
check('重新启用后待办仍在赵巡检名下(不自动拿回)', t['data']['assignee_name'] == '赵巡检', t['data'])

# ================================================== 2. 停用整改人 → 在办整改单退回并可被领取
# 赵巡检提交一个异常任务，整改单由钱整改领取
tid2 = publish(I2, '整改人停用-整改单退池')
c, d = call('POST', f'/tasks/{tid2}/submit/', I2, {
    'items': [{'name': '消防', 'result': 'issue', 'description': '灭火器失效'},
              {'name': '照明', 'result': 'normal'}],
})
check('提交异常生成整改单', c == 200 and d['data']['open_order_count'] == 1, d)
_, ods = call('GET', f'/orders/?task={tid2}', I2)
oid = ods['data'][0]['id']
c, d = call('POST', f'/orders/{oid}/claim/', R1)
check('钱整改领取整改单', c == 200 and d['data']['status'] == 'processing', d)
# 停用钱整改（id=4）
c, d = call('POST', '/users/4/active/', P, {'is_active': False})
check('停用整改人返回整改单交接统计', c == 200 and d['data']['handoff']['order_count'] >= 1, d)
_, o = call('GET', f'/orders/{oid}/', R2)
check('整改单退回公共池且待领取', o['data']['assignee_name'] is None and o['data']['status'] == 'pending', o['data'])
c, d = call('POST', f'/orders/{oid}/claim/', R2)
check('其他整改人可领取被释放整改单', c == 200 and d['data']['assignee_name'] == '孙整改', d)
# 恢复钱整改
call('POST', '/users/4/active/', P, {'is_active': True})
_, o = call('GET', f'/orders/{oid}/', R2)
check('整改人重新启用后整改单仍在孙整改名下', o['data']['assignee_name'] == '孙整改', o['data'])

# ================================================== 3. 指定接管人
tid3 = publish(I1, '停用-指定接管')
# 准备一个钱整改名下的整改单
c, d = call('POST', f'/tasks/{tid3}/submit/', I1, {
    'items': [{'name': '照明', 'result': 'issue', 'description': '走廊灯不亮'}],
})
_, ods = call('GET', f'/orders/?task={tid3}', I1)
oid3 = ods['data'][0]['id']
c, d = call('POST', f'/orders/{oid3}/claim/', R1)
check('钱整改领取(为接管做准备)', c == 200, d)
# 停用李巡检(2)，指定赵巡检(3)接管
c, d = call('POST', '/users/2/active/', P, {'is_active': False, 'takeover_user_id': 3})
check('停用并指定接管成功', c == 200 and d['data']['handoff']['takeover'] == '赵巡检', d)
_, t = call('GET', f'/tasks/{tid3}/', I2)
check('任务直接归属接管巡检员', t['data']['assignee_name'] == '赵巡检' and t['data']['status'] in ('claimed', 'submitted', 'returned'), t['data'])
# 该任务已被提交（submitted），接管人可复验
check('接管后任务保留待整改状态', t['data']['status'] == 'submitted', t['data'])
# 公共池中不应出现该任务
_, pool = call('GET', '/tasks/?scope=pool', I2)
check('被接管任务不在公共池', all(x['id'] != tid3 for x in pool['data']), '出现在公共池')

# 停用钱整改(4)，指定孙整改(5)接管整改单
c, d = call('POST', '/users/4/active/', P, {'is_active': False, 'takeover_user_id': 5})
check('停用整改人并指定接管', c == 200 and d['data']['handoff']['takeover'] == '孙整改', d)
_, o = call('GET', f'/orders/{oid3}/', R2)
check('整改单归属接管整改人', o['data']['assignee_name'] == '孙整改', o['data'])
# 接管人可直接提交处理结果（processing 状态保留或转 processing）
c, d = call('POST', f'/orders/{oid3}/submit/', R2, {'note': '更换走廊灯'})
check('接管整改人可直接处理', c == 200 and d['data']['status'] == 'submitted', d)
# 接管巡检员可复验并关闭
c, d = call('POST', f'/orders/{oid3}/recheck/', I2, {'passed': True})
check('接管巡检员可复验', c == 200 and d['data']['status'] == 'verified', d)
c, d = call('POST', f'/tasks/{tid3}/close/', I2)
check('接管巡检员可闭环关闭', c == 200 and d['data']['status'] == 'done', d)
# 恢复
call('POST', '/users/2/active/', P, {'is_active': True})
call('POST', '/users/4/active/', P, {'is_active': True})

# ================================================== 4. 非法接管
tid4 = publish(I1, '非法接管校验')
# 角色不一致（让巡检员接管整改人）
c, d = call('POST', '/users/4/active/', P, {'is_active': False, 'takeover_user_id': 2})
check('角色不一致接管被拒(400)且不停用', c == 400 and d['code'] == 'ROLE_MISMATCH', d)
# 本人接管本人
c, d = call('POST', '/users/2/active/', P, {'is_active': False, 'takeover_user_id': 2})
check('本人接管被拒(400)', c == 400 and d['code'] == 'ROLE_MISMATCH', d)
# 接管停用账号：先停用赵巡检(3)，再让李巡检(2)停用指定赵接管
call('POST', '/users/3/active/', P, {'is_active': False})
c, d = call('POST', '/users/2/active/', P, {'is_active': False, 'takeover_user_id': 3})
check('接管停用账号被拒(409)且整体回滚', c == 409 and d['code'] == 'TAKEOVER_TARGET_DISABLED', d)
# 回滚校验：李巡检未被停用，tid4 仍在其名下且历史无交接（用物业令牌读取）
c, _ = call('POST', '/auth/login/', body={'username': 'xunjian1', 'password': 'demo123456'})
check('接管失败时持有者未被停用', c == 200, f'login={c}')
_, tt = call('GET', f'/tasks/{tid4}/', P)
check('接管失败待办仍在原持有者名下', tt['data']['assignee'] == 2, tt)
_, th = call('GET', f'/tasks/{tid4}/timeline/', P)
check('接管失败不产生交接历史',
      all(e['action'] not in ('handoff_user', 'handoff_pool') for e in th['data']),
      [e['action'] for e in th['data']])
# 全部恢复
call('POST', '/users/2/active/', P, {'is_active': True})
call('POST', '/users/3/active/', P, {'is_active': True})

# ================================================== 5. 并发：停用 vs 领取，只有一个结果
tid5 = publish(I1, '并发停用-领取')
fired = []


def claim(_):
    return call('POST', f'/tasks/{tid5}/claim/', I2)


def deactivate():
    return call('POST', '/users/2/active/', P, {'is_active': False})


# 让停用与多个领取同时竞争
with ThreadPoolExecutor(max_workers=11) as ex:
    futs = [ex.submit(deactivate)] + [ex.submit(claim, i) for i in range(10)]
    race = [f.result() for f in futs]
deact_result = race[0]
claim_results = race[1:]
claim_ok = [r for r in claim_results if r[0] == 200]
_, final = call('GET', f'/tasks/{tid5}/', P)
fa = final['data']
check('停用接口执行完成', deact_result[0] == 200, deact_result)
# 唯一一致性：任务要么被某个领取者拿到，要么被停用退池；领取成功者至多 1 人
check('并发竞争中领取成功者不超过1人', len(claim_ok) <= 1, f'{len(claim_ok)} 人领取成功')
if claim_ok:
    # 若领取先于停用：赵巡检拿到，停用交接时因任务已不属于李巡检，任务留在赵名下
    check('领取先成功则任务归属赵巡检', fa['assignee_name'] == '赵巡检', fa)
else:
    # 若停用先成功：任务退池待领取，无归属
    check('停用先成功则任务退回公共池', fa['assignee_name'] is None and fa['status'] == 'pending', fa)
    c, d = call('POST', f'/tasks/{tid5}/claim/', I2)
    check('退池后可被领取', c == 200, d)
# 李巡检最终确为停用
_, u2 = call('GET', '/users/?role=inspector', P)
li = next((x for x in u2['data'] if x['username'] == 'xunjian1'), None)
check('李巡检最终为停用状态', li and li['is_active'] is False, li)
call('POST', '/users/2/active/', P, {'is_active': True})

# ================================================== 6. 挂起升级单一并解除
tid6 = publish(I1, '停用-升级单解除')
# 通过 Django ORM 为该任务插入一条挂起升级单（模拟超期扫描结果）
import os
import subprocess
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
subprocess.run([
    sys.executable, os.path.join(backend_dir, 'manage.py'),
    'shell', '-c',
    (
        "from app.apps.escalation.models import Escalation;"
        f"Escalation.objects.get_or_create(target_type='task',target_id={tid6},status='open',"
        "defaults={'reason':'测试挂起升级单','level':'supervisor'})"
    ),
], check=True, capture_output=True, cwd=backend_dir, env=os.environ.copy())
S = login('zhuguan')
_, esc_before = call('GET', '/escalations/?status=open', S)
check('停用前存在该任务的挂起升级单', any(x['target_id'] == tid6 for x in esc_before['data']), esc_before['data'])
# 停用李巡检(2)，退池
c, d = call('POST', '/users/2/active/', P, {'is_active': False})
check('停用成功', c == 200, d)
_, esc_after = call('GET', '/escalations/?status=open', S)
check('挂起升级单随交接一并解除', not any(x['target_id'] == tid6 for x in esc_after['data']), esc_after['data'])
_, esc_resolved = call('GET', '/escalations/?status=resolved', S)
match = [x for x in esc_resolved['data'] if x['target_id'] == tid6]
check('解除的升级单带交接说明', bool(match) and '停用' in (match[0]['handle_note'] or ''), match)
call('POST', '/users/2/active/', P, {'is_active': True})

passed = sum(1 for _, ok in results if ok)
print(f'\n==== {passed}/{len(results)} passed ====')
raise SystemExit(0 if passed == len(results) else 1)
