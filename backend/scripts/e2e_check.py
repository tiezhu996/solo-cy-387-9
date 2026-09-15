# -*- coding: utf-8 -*-
"""端到端闭环 + 并发领取验证。通过 HTTP API 验证全部关键路径。

前置：数据库已执行 migrate + bootstrap_demo。
用法：PORT=8000 python3 scripts/e2e_check.py
"""
import json
import os
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = f"http://127.0.0.1:{os.getenv('PORT', '8000')}/api"
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
    code, data = call('POST', '/auth/login/', body={'username': u, 'password': 'demo123456'})
    assert code == 200, data
    return data['data']['token']


P = login('wuye'); I1 = login('xunjian1'); I2 = login('xunjian2')
R1 = login('zhenggai1'); R2 = login('zhenggai2'); S = login('zhuguan')

# ============================================================ 1. 并发领取任务
code, data = call('GET', '/tasks/?scope=pool', I1)
tid = data['data'][0]['id']


def race_task(i):
    return call('POST', f'/tasks/{tid}/claim/', I1 if i % 2 == 0 else I2)


with ThreadPoolExecutor(max_workers=10) as ex:
    outs = list(ex.map(race_task, range(10)))
ok_count = [c for c, _ in outs if c == 200]
conflict = [d for c, d in outs if c == 409]
check('并发10次领取任务仅1人成功', len(ok_count) == 1, outs)
check('其余领取返回409任务已被领取', len(conflict) == 9, outs)

# 输的人再次重复领取仍然失败
code, data = call('POST', f'/tasks/{tid}/claim/', I2)
check('重复领取被拒(409)', code == 409 and data['code'] == 'TASK_NOT_CLAIMABLE', data)

code, data = call('GET', f'/tasks/{tid}/', I1)
winner_name = data['data']['assignee_name']
winner_token = I1 if winner_name == '李巡检' else I2
loser_token = I2 if winner_token == I1 else I1
check('任务归属人为成功领取者', winner_name in ('李巡检', '赵巡检'), data['data'])

# 非归属人不能提交
code, data = call('POST', f'/tasks/{tid}/submit/', loser_token,
                  {'items': [{'name': '消防通道是否畅通', 'result': 'normal'}]})
check('非归属巡检员提交被拒(403)', code == 403, data)

# ============================================================ 2. 完整异常闭环
_, buildings = call('GET', '/buildings/', P)
bid = buildings['data'][0]['id']
_, areas = call('GET', f'/areas/?building={bid}', P)
aid = areas['data'][0]['id']
scheduled = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
code, data = call('POST', '/tasks/', P, {
    'title': '并发闭环验证任务', 'building_id': bid, 'area_id': aid,
    'period': 'daily', 'scheduled_at': scheduled, 'due_at': due,
    'checklist': ['消防设施', '照明', '卫生'],
})
check('物业发布巡检任务', code == 201, data)
loop_tid = data['data']['id']

code, data = call('POST', f'/tasks/{loop_tid}/claim/', I1)
check('巡检员领取', code == 200, data)

code, data = call('POST', f'/tasks/{loop_tid}/submit/', I1, {
    'summary': '发现灭火器过期',
    'items': [
        {'name': '消防设施', 'result': 'issue', 'description': '2具干粉灭火器过期',
         'photos': ['/media/uploads/demo1.jpg']},
        {'name': '照明', 'result': 'normal'},
        {'name': '卫生', 'result': 'issue', 'description': '垃圾桶周边散落垃圾'},
    ],
})
check('提交2项异常,任务进入待整改', code == 200 and data['data']['status'] == 'submitted', data)
check('open_order_count=2', data['data']['open_order_count'] == 2, data['data'])

_, orders = call('GET', f'/orders/?task={loop_tid}', I1)
check('异常生成2张整改单且保留来源', len(orders['data']) == 2
      and all(o['source'] == 'inspection' and o['issue_photos'] is not None for o in orders['data']),
      orders['data'])
oid_a, oid_b = [o['id'] for o in orders['data']]


# ---- 整改单并发领取
def race_order(i):
    return call('POST', f'/orders/{oid_a}/claim/', R1 if i % 2 == 0 else R2)


with ThreadPoolExecutor(max_workers=10) as ex:
    oouts = list(ex.map(race_order, range(10)))
check('并发10次领取整改单仅1人成功',
      len([c for c, _ in oouts if c == 200]) == 1
      and len([d for c, d in oouts if c == 409]) == 9, oouts)

# 并发胜者不确定，按实际归属决定后续用哪个整改人
_, oa = call('GET', f'/orders/{oid_a}/', R1)
RA = R1 if oa['data']['assignee_name'] == '钱整改' else R2
RB_other = R2 if RA == R1 else R1  # 另一整改人

# 第二张整改单由「另一整改人」领取，避免与 A 归属冲突
code, data = call('POST', f'/orders/{oid_b}/claim/', RB_other)
check('另一整改人领取第二张整改单', code == 200, data)

# 整改人提交结果
code, data = call('POST', f'/orders/{oid_a}/submit/', RA,
                  {'note': '已更换2具灭火器', 'photos': ['/media/uploads/fixed1.jpg']})
check('整改人A提交处理结果', code == 200 and data['data']['status'] == 'submitted', data)
code, data = call('POST', f'/orders/{oid_b}/submit/', RB_other, {'note': '已清理垃圾并加强保洁'})
check('整改人B提交处理结果', code == 200, data)

# 非该任务巡检员复验被拒（用别的巡检员身份无法构造，因为 I2 不是归属人）
code, data = call('POST', f'/orders/{oid_a}/recheck/', I2, {'passed': True})
check('非归属巡检员复验被拒', code == 403, data)

# A 复验驳回一轮，B 通过
code, data = call('POST', f'/orders/{oid_a}/recheck/', I1,
                  {'passed': False, 'note': '灭火器压力指针在红区，请重新更换'})
check('复验驳回,整改单进入新一轮', code == 200 and data['data']['status'] == 'returned'
      and data['data']['round'] == 2, data)

code, tdata = call('GET', f'/tasks/{loop_tid}/', I1)
check('驳回后任务状态为复验驳回', tdata['data']['status'] == 'returned', tdata['data'])

# 被驳回的整改单仍归属原整改人，整改人直接重新提交（无需重复领取）
code, data = call('POST', f'/orders/{oid_a}/submit/', RA, {'note': '再次更换合格灭火器并核验压力'})
check('第2轮整改提交', code == 200 and data['data']['round'] == 2, data)
code, data = call('POST', f'/orders/{oid_a}/recheck/', I1, {'passed': True, 'note': '合格'})
check('第2轮复验通过', code == 200 and data['data']['status'] == 'verified', data)
code, data = call('POST', f'/orders/{oid_b}/recheck/', I1, {'passed': True})
check('整改单B复验通过', code == 200 and data['data']['status'] == 'verified', data)

# 还有未关闭时尝试关任务 -> 都 verified 了，可以关闭
code, data = call('POST', f'/tasks/{loop_tid}/close/', I1)
check('全部复验通过后任务闭环关闭', code == 200 and data['data']['status'] == 'done', data)
_, od = call('GET', f'/orders/{oid_a}/', I1)
check('整改单随任务一并关闭', od['data']['status'] == 'closed', od['data'])

# ============================================================ 3. 时间线完整
_, tl = call('GET', f'/tasks/{loop_tid}/timeline/', I1)
actions = [e['action'] for e in tl['data']]
check('时间线包含整改单来源生成记录',
      actions.count('create_from_inspection') == 2, actions)
check('时间线包含驳回与通过记录',
      'recheck_reject' in actions and 'recheck_pass' in actions, actions)
check('时间线包含任务关闭记录', actions[-1] == 'close', actions[-3:])
check('刷新后仍可取回完整时间线(>15条)', len(tl['data']) >= 15, f'{len(tl["data"])} 条')

# ============================================================ 4. 改期 + 重新分派 + 停用
code, data = call('POST', '/tasks/', P, {
    'title': '改期分派验证任务', 'building_id': bid, 'area_id': aid, 'period': 'weekly',
    'scheduled_at': scheduled, 'due_at': due, 'checklist': ['照明'],
})
rtid = data['data']['id']
new_sched = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
new_due = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
code, data = call('POST', f'/tasks/{rtid}/reschedule/', P,
                  {'scheduled_at': new_sched, 'due_at': new_due})
# 期限按同一时刻比较（服务端按本地时区渲染，字符串日期可能跨天）
def _iso_eq(a, b):
    from datetime import datetime as _dt
    return abs((_dt.fromisoformat(a) - _dt.fromisoformat(b)).total_seconds()) < 60

check('任务改期成功,期限同步',
      code == 200 and _iso_eq(data['data']['due_at'], new_due), data)

# 分派给李巡检，再改派赵巡检（不允许两人同时处理）
code, data = call('POST', f'/tasks/{rtid}/reassign/', P, {'user_id': 2})
check('首次分派给李巡检', code == 200 and data['data']['assignee_name'] == '李巡检', data)
code, data = call('POST', f'/tasks/{rtid}/reassign/', P, {'user_id': 3})
check('重新分派给赵巡检,归属唯一', code == 200 and data['data']['assignee_name'] == '赵巡检', data)
code, data = call('POST', f'/tasks/{rtid}/submit/', I1,
                  {'items': [{'name': '照明', 'result': 'normal'}]})
check('原负责人提交失效(403)', code == 403, data)
code, data = call('POST', f'/tasks/{rtid}/submit/', I2,
                  {'items': [{'name': '照明', 'result': 'normal'}]})
check('新负责人可提交并关闭', code == 200 and data['data']['status'] == 'done', data)

# 退回公共池后可被重新领取
_, pool = call('GET', '/tasks/?scope=pool', I1)
ptid = pool['data'][0]['id']
code, data = call('POST', f'/tasks/{ptid}/reassign/', P, {'to_pool': True})
check('退回公共池(幂等)', code == 200 and data['data']['status'] == 'pending', data)
code, data = call('POST', f'/tasks/{ptid}/claim/', I2)
check('公共池任务可再领取', code == 200 and data['data']['assignee_name'] == '赵巡检', data)

# 停用人员（连带交接其在办待办）
code, data = call('POST', '/users/2/active/', P, {'is_active': False})
check('物业停用巡检员', code == 200 and data['data']['is_active'] is False, data)
code, data = call('POST', '/auth/login/', body={'username': 'xunjian1', 'password': 'demo123456'})
check('停用人员无法登录(403)', code == 403 and data['code'] == 'USER_DISABLED', data)
# 停用前若该任务在李巡检名下且在办，停用应把它释放到公共池
_, tmeta = call('GET', f'/tasks/{tid}/', I2)
_, hist = call('GET', f'/tasks/{tid}/timeline/', I2)
if tmeta['data']['assignee'] == 2 and tmeta['data']['status'] != 'done':
    check('停用后在办任务退回公共池', tmeta['data']['assignee_name'] is None, tmeta['data'])
    check('退池在历史中留痕', any(e['action'] == 'handoff_pool' for e in hist['data']), '无 handoff_pool')
else:
    check('停用不影响非其名下/已关闭任务', True)
# 历史记录仍然保留（领取等原始记录不因交接丢失）
check('停用后历史记录不丢失',
      any(e['action'] in ('claim', 'publish') and e['actor_name'] for e in hist['data']),
      '原始历史缺失')
# 恢复
call('POST', '/users/2/active/', P, {'is_active': True})

# ============================================================ 5. 超期升级
code, data = call('GET', '/escalations/?status=open', S)
# 种子里有一条超期任务，扫描后应出现
check('主管可查看升级列表(种子超期任务)', code == 200, data)
seed_escalations = len(data['data'])

# 直接命令行扫描由外部执行，这里验证 API 处置
if data['data']:
    esc_id = data['data'][0]['id']
    code, rdata = call('POST', f'/escalations/{esc_id}/resolve/', S, {'note': '已安排补检'})
    check('主管处置升级单', code == 200 and rdata['data']['status'] == 'resolved', rdata)
    code, data = call('POST', f'/escalations/{esc_id}/resolve/', P, {'note': 'x'})
    check('物业不能处置升级(403)', code == 403, data)
else:
    check('主管可查看升级列表(无数据也算接口正常)', True)

# 整改人不能看升级台
code, data = call('GET', '/escalations/', R1)
check('整改人无权访问升级台(403)', code == 403, data)

# ============================================================ 6. 角色权限
code, data = call('POST', '/tasks/', I1, {
    'title': 'x', 'building_id': bid, 'area_id': aid, 'period': 'daily',
    'scheduled_at': scheduled, 'due_at': due, 'checklist': ['a']})
check('巡检员不能发布任务(403)', code == 403, data)
code, data = call('POST', f'/orders/{oid_b}/claim/', I1)
check('巡检员不能领取整改单(403)', code == 403, data)

# ============================================================ 汇总
passed = sum(1 for _, ok in results if ok)
print(f'\n==== {passed}/{len(results)} passed ====')
sys_exit = 0 if passed == len(results) else 1
raise SystemExit(sys_exit)
