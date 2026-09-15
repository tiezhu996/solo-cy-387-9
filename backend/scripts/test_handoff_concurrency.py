# -*- coding: utf-8 -*-
"""停用交接并发测试（可重复运行，无 mock、无内存替身、无串行化）。

工作方式：
1. 为本次运行创建一次性 SQLite 数据库，迁移 + 种子后，用 **gunicorn 多 worker**
   启动真实后端——每个请求由独立进程上的独立数据库连接处理，存在真实锁竞争；
2. 每个并发场景自建专属用户与任务/整改单，线程在 threading.Barrier 上同时释放，
   让「巡检员/整改人领取」与「物业停用」在服务器侧真正并发；
3. 断言与执行次序无关：无论领取先成功还是停用先成功，只允许一个一致结果；
4. 跑完自动终止进程并删除数据库文件，反复执行结论一致，不依赖固定执行顺序。

用法：
    python3 scripts/test_handoff_concurrency.py
环境变量：
    ROUNDS=6     每种场景的并发轮数（默认 6）
    CLAIMERS=8   每轮参与并发领取的请求数（默认 8）
    WORKERS=4    gunicorn worker 进程数（默认 4）

退出码 0 表示全部一致；非 0 表示发现归属错误/重复成功/失败方改数/历史缺失。
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROUNDS = int(os.getenv('ROUNDS', '6'))
CLAIMERS = int(os.getenv('CLAIMERS', '8'))
WORKERS = int(os.getenv('WORKERS', '4'))
PASSWORD = 'demo123456'

failures = []


def check(name, cond, detail=''):
    print(('  PASS ' if cond else '  FAIL ') + name + ('' if cond else f' :: {detail}'))
    if not cond:
        failures.append(f'{name} | {detail}')


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def make_call(base):
    def call(method, path, token=None, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        if token:
            req.add_header('Authorization', f'Token {token}')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    return call


def wait_ready(call):
    deadline = time.time() + 40
    last = None
    while time.time() < deadline:
        try:
            code, _ = call('GET', '/auth/demo-accounts/')
            if code == 200:
                return True
        except Exception as e:  # 服务尚未就绪
            last = e
        time.sleep(0.3)
    raise RuntimeError(f'后端未在限定时间内就绪: {last}')


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --------------------------------------------------------------------------- #
# 一次性真实后端（gunicorn 多 worker，独立连接）
# --------------------------------------------------------------------------- #
class RealServer:
    def __init__(self):
        self.db_path = Path(tempfile.gettempdir()) / f'patrolloop_conc_{os.getpid()}.sqlite3'
        for suffix in ('', '-wal', '-shm'):
            p = Path(str(self.db_path) + suffix)
            if p.exists():
                p.unlink()
        self.db_url = f'sqlite:///{self.db_path}'
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}/api'
        self.log_path = Path(tempfile.gettempdir()) / f'patrolloop_conc_{os.getpid()}.log'
        self.proc = None

    def _manage(self, *args):
        env = {**os.environ, 'DATABASE_URL': self.db_url}
        r = subprocess.run([sys.executable, 'manage.py', *args], cwd=BACKEND_DIR,
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'manage.py {args} failed:\n{r.stdout}\n{r.stderr}')

    def start(self):
        self._manage('migrate', '--noinput')
        self._manage('bootstrap_demo')
        env = {**os.environ, 'DATABASE_URL': self.db_url, 'DJANGO_DEBUG': 'false'}
        self.log_fp = open(self.log_path, 'w')
        self.proc = subprocess.Popen(
            [
                sys.executable, '-m', 'gunicorn', 'app.wsgi:application',
                '--bind', f'127.0.0.1:{self.port}',
                '--workers', str(WORKERS), '--threads', '1',
                '--timeout', '60', '--access-logfile', '-', '--error-logfile', '-',
                '--log-level', 'warning',
            ],
            cwd=BACKEND_DIR, env=env, stdout=self.log_fp, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        wait_ready(make_call(self.base))
        print(f'[server] gunicorn {WORKERS} workers @ 127.0.0.1:{self.port} '
              f'db={self.db_path.name} log={self.log_path.name}')

    def stop(self):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, 9)
            self.proc.wait(timeout=10)
        if hasattr(self, 'log_fp'):
            self.log_fp.close()
        for path in (self.db_path, Path(str(self.db_path) + '-wal'),
                     Path(str(self.db_path) + '-shm'), self.log_path):
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass


# --------------------------------------------------------------------------- #
# 场景构造
# --------------------------------------------------------------------------- #
def create_user(call, token, username, name, role):
    code, data = call('POST', '/users/', token, {
        'username': username, 'name': name, 'role': role,
        'phone': '13800000000', 'password': PASSWORD,
    })
    assert code == 201, data
    return data['data']['id']


def login(call, username):
    code, data = call('POST', '/auth/login/', None, {'username': username, 'password': PASSWORD})
    assert code == 200, data
    return data['data']['token']


def pick_building_area(call, token):
    _, b = call('GET', '/buildings/', token)
    bid = b['data'][0]['id']
    _, ar = call('GET', f'/areas/?building={bid}', token)
    return bid, ar['data'][0]['id']


def publish(call, token, bid, aid, assignee_id, title, checklist):
    now = datetime.now(timezone.utc)
    code, data = call('POST', '/tasks/', token, {
        'title': title, 'building_id': bid, 'area_id': aid, 'period': 'daily',
        'scheduled_at': (now + timedelta(hours=1)).isoformat(),
        'due_at': (now + timedelta(days=2)).isoformat(),
        'checklist': checklist, 'assignee_id': assignee_id,
    })
    assert code == 201, data
    return data['data']['id']


def race(call, barrier, fn):
    """所有参与线程在同一屏障点释放，制造服务器侧真实并发。"""
    barrier.wait()
    return fn()


# --------------------------------------------------------------------------- #
# 断言
# --------------------------------------------------------------------------- #
def assert_handoff_events_valid_task(entries, holder_name):
    """从时间线重放任务状态机，校验每条交接事件都作用在真实归属上。

    handoff_pool/handoff_user 发生时，当前归属人必须是被停用者本人；
    若资源已被竞争者通过 claim 拿走，停用方再写交接即「幻象历史」，必须失败。
    """
    owner = None
    status = None
    problems = []
    for e in entries:
        a = e['action']
        if a in ('publish', 'direct_assign'):
            if a == 'direct_assign':
                owner = holder_name
            status = e['to_status'] or status
        elif a == 'claim':
            owner = e['actor_name']
            status = e['to_status'] or status
        elif a in ('handoff_pool', 'handoff_user'):
            if owner != holder_name:
                problems.append(
                    f"交接事件 {a} 时归属人为 {owner!r}，非被停用者 {holder_name!r}（失败方改动了数据/历史）"
                )
            if a == 'handoff_pool':
                owner = None
                status = e['to_status']
            else:
                owner = e['actor_name']
                status = e['to_status']
        elif a in ('submit_with_issue', 'submit_normal_close', 'recheck_reject',
                   'all_verified', 'close'):
            status = e['to_status'] or status
    check('[task] 每条交接事件都作用于被停用者真实在办资源', not problems, '; '.join(problems))


def assert_handoff_events_valid_order(entries, holder_name):
    """整改单维度的交接事件重放校验。"""
    owner = None
    problems = []
    for e in entries:
        a = e['action']
        if a == 'create_from_inspection':
            owner = None
        elif a == 'claim':
            owner = e['actor_name']
        elif a in ('handoff_pool', 'handoff_user'):
            if owner != holder_name:
                problems.append(
                    f"整改单交接事件 {a} 时归属人为 {owner!r}，非被停用者 {holder_name!r}"
                )
            owner = None if a == 'handoff_pool' else e['actor_name']
        elif a in ('submit_resolution', 'recheck_pass', 'recheck_reject',
                   'close_with_task'):
            pass
    check('[order] 每条交接事件都作用于被停用者真实在办整改单', not problems, '; '.join(problems))


def assert_task_consistency(call, rival_token, task_id, holder_id, rival_id,
                            claim_codes, kind, holder_name):
    """次序无关的不变量校验（同一波次内允许「停用释放→竞争者抢到」）。"""
    _, t = call('GET', f'/tasks/{task_id}/', rival_token)
    task = t['data']
    _, tl = call('GET', f'/tasks/{task_id}/timeline/', rival_token)
    entries = [e for e in tl['data'] if e['target_type'] == 'task']
    actions = [e['action'] for e in entries]
    pool_handoffs = [e for e in entries if e['action'] == 'handoff_pool']
    claim_won = sum(1 for c in claim_codes if c == 200)

    # 事件级重放：交接事件必须作用于被停用者真实在办资源（抓幻象历史/失败方改动）
    assert_handoff_events_valid_task(entries, holder_name)

    # 1) 重复成功：并发领取至多 1 次
    check(f'[{kind}] 任务并发领取成功者<=1', claim_won <= 1, f'{claim_won} 次, codes={claim_codes}')
    # 2) 失败方拿到冲突码而非服务器错误（5xx 即锁处理缺陷）
    check(f'[{kind}] 任务领取失败方均为409而非5xx',
          all(c in (200, 409) for c in claim_codes), f'codes={claim_codes}')
    # 3) 退池交接至多 1 次（双停用/幻象交接会 >1）
    check(f'[{kind}] 任务退池交接至多1次', len(pool_handoffs) <= 1,
          f'{len(pool_handoffs)} 条 handoff_pool')

    # 4) 最终归属只能是竞争者或公共池，绝不能停在被停用者名下（死信）
    check(f'[{kind}] 任务不停留在停用者名下',
          task['assignee'] in (rival_id, None) and task['assignee'] != holder_id,
          f"assignee={task['assignee']}({task['assignee_name']})")

    # 5) 状态合法（claimed 场景只会是 claimed/pending；issue 场景保持 submitted）
    legal = ['claimed', 'pending'] if kind == 'claimed' else ['submitted', 'returned']
    check(f'[{kind}] 任务最终状态合法', task['status'] in legal, f"status={task['status']}")

    # 6) 归属/历史链必须自洽
    if task['assignee'] == rival_id:
        # 竞争者持有：要么「领取抢在停用前」(0 退池)，要么「停用退池后被竞争者领走」(1 退池 + 其后有 claim)
        last_pool_idx = max((i for i, a in enumerate(actions) if a == 'handoff_pool'), default=-1)
        later_claim = any(a == 'claim' for a in actions[last_pool_idx + 1:]) if last_pool_idx >= 0 else True
        check(f'[{kind}] 竞争者持有时历史链自洽',
              len(pool_handoffs) == 0 or (len(pool_handoffs) == 1 and later_claim),
              f'actions={actions}')
    else:
        # 公共池：必须恰好 1 次退池交接、其后无人再领取
        last_pool_idx = max((i for i, a in enumerate(actions) if a == 'handoff_pool'), default=-1)
        later_claim = any(a == 'claim' for a in actions[last_pool_idx + 1:]) if last_pool_idx >= 0 else False
        check(f'[{kind}] 公共池状态有且仅有一次退池且其后无领取',
              len(pool_handoffs) == 1 and not later_claim, f'actions={actions}')
        check(f'[{kind}] 并发领取无一成功(任务在池)', claim_won == 0, f'claim_won={claim_won}')

    # 7) 原始历史不缺失（交接不得覆盖旧记录）
    if kind == 'claimed':
        check(f'[{kind}] 保留发布/指派历史',
            ('direct_assign' in actions or 'publish' in actions or 'claim' in actions), str(actions))
    else:
        check(f'[{kind}] 保留发布与提交异常历史',
              'submit_with_issue' in actions and 'direct_assign' in actions, str(actions))
    return task, task['assignee'] == rival_id


def assert_order_consistency(call, rival_token, order, claim_codes, holder_rect_id,
                             rival_rect_id, kind, holder_name):
    """整改单次序无关不变量：竞争者处理中 或 公共池待领取，二选一。"""
    _, od = call('GET', f'/orders/{order["id"]}/', rival_token)
    o = od['data']
    _, tl = call('GET', f'/tasks/{order["task"]}/timeline/', rival_token)
    entries = [e for e in tl['data']
               if e['target_type'] == 'rectification_order' and e['target_id'] == order['id']]
    actions = [e['action'] for e in entries]
    pool_handoffs = [e for e in entries if e['action'] == 'handoff_pool']
    claim_won = sum(1 for c in claim_codes if c == 200)

    # 事件级重放校验
    assert_handoff_events_valid_order(entries, holder_name)

    check(f'[{kind}] 整改单并发领取成功者<=1', claim_won <= 1, f'codes={claim_codes}')
    check(f'[{kind}] 整改单领取失败方均为409而非5xx',
          all(c in (200, 409) for c in claim_codes), f'codes={claim_codes}')
    check(f'[{kind}] 整改单退池交接至多1次', len(pool_handoffs) <= 1,
          f'{len(pool_handoffs)} 条 handoff_pool')
    check(f'[{kind}] 整改单不停留在停用整改人名下',
          o['assignee'] in (rival_rect_id, None) and o['assignee'] != holder_rect_id,
          f"assignee={o['assignee']}({o['assignee_name']})")

    if o['assignee'] == rival_rect_id:
        check(f'[{kind}] 竞争者持有时整改单为processing', o['status'] == 'processing',
              f"status={o['status']}")
        last_pool_idx = max((i for i, a in enumerate(actions) if a == 'handoff_pool'), default=-1)
        later_claim = any(a == 'claim' for a in actions[last_pool_idx + 1:]) if last_pool_idx >= 0 else True
        check(f'[{kind}] 竞争者持有时整改单历史链自洽',
              len(pool_handoffs) == 0 or (len(pool_handoffs) == 1 and later_claim),
              f'actions={actions}')
    else:
        check(f'[{kind}] 公共池整改单为pending可再领取', o['status'] == 'pending',
              f"status={o['status']}")
        last_pool_idx = max((i for i, a in enumerate(actions) if a == 'handoff_pool'), default=-1)
        later_claim = any(a == 'claim' for a in actions[last_pool_idx + 1:]) if last_pool_idx >= 0 else False
        check(f'[{kind}] 公共池整改单有且仅有一次退池且其后无领取',
              len(pool_handoffs) == 1 and not later_claim, f'actions={actions}')
        check(f'[{kind}] 并发领取无一成功(整改单在池)', claim_won == 0, f'claim_won={claim_won}')

    check(f'[{kind}] 整改单保留来源生成与领取历史',
          'create_from_inspection' in actions and 'claim' in actions, str(actions))
    return o['assignee'] == rival_rect_id


def assert_user_disabled(call, username):
    code, data = call('POST', '/auth/login/', None, {'username': username, 'password': PASSWORD})
    return code == 403 and data.get('code') == 'USER_DISABLED'


# --------------------------------------------------------------------------- #
# 同一人：本人领取 vs 停用本人（本次要修复的核心竞争）
# --------------------------------------------------------------------------- #
def run_self_round(server, idx):
    """同一用户 X 的「领取公共池待办」与「物业停用 X」同时发生。

    合法终态唯一收敛为：X 停用、待办在公共池且可被他人领取（X 领取失败，或
    领取成功后立刻被停用交接释放）。绝不能停在已停用的 X 名下。
    """
    call = make_call(server.base)
    ptoken = login(call, 'wuye')
    bid, aid = pick_building_area(call, ptoken)
    tag = f's{idx}_{int(time.time() * 1000) % 100000}'

    insp = f'si_{tag}'
    rect = f'sr_{tag}'
    other_insp = f'so_{tag}'
    other_rect = f'sr2_{tag}'
    i_id = create_user(call, ptoken, insp, '自领巡检员', 'inspector')
    o_id = create_user(call, ptoken, other_insp, '接手巡检员', 'inspector')
    r_id = create_user(call, ptoken, rect, '自领整改人', 'rectifier')
    or_id = create_user(call, ptoken, other_rect, '接手整改人', 'rectifier')
    i_tok = login(call, insp)
    o_tok = login(call, other_insp)
    r_tok = login(call, rect)
    or_tok = login(call, other_rect)

    # 公共池任务（无归属）由本人去领取；另一任务产生一张公共池整改单
    tid = publish(call, ptoken, bid, aid, None, f'自领任务-{tag}', ['消防', '照明'])
    holder_insp = f'sh_{tag}'
    create_user(call, ptoken, holder_insp, '提交巡检员', 'inspector')
    h_tok = login(call, holder_insp)
    tid2 = publish(call, ptoken, bid, aid, None, f'自领整改来源-{tag}', ['消防', '照明'])
    c, _ = call('POST', f'/tasks/{tid2}/claim/', h_tok)
    assert c == 200
    c, _ = call('POST', f'/tasks/{tid2}/submit/', h_tok, {
        'items': [
            {'name': '消防', 'result': 'issue', 'description': '需整改'},
            {'name': '照明', 'result': 'normal'},
        ]})
    assert c == 200
    _, ods = call('GET', f'/orders/?task={tid2}', h_tok)
    oid = ods['data'][0]['id']

    parties = [
        ('deact_inspector', lambda: call('POST', f'/users/{i_id}/active/', ptoken, {'is_active': False})),
        ('deact_rectifier', lambda: call('POST', f'/users/{r_id}/active/', ptoken, {'is_active': False})),
    ]
    parties += [
        (f'claim_task_{k}', (lambda: call('POST', f'/tasks/{tid}/claim/', i_tok)))
        for k in range(CLAIMERS)
    ]
    parties += [
        (f'claim_order_{k}', (lambda: call('POST', f'/orders/{oid}/claim/', r_tok)))
        for k in range(CLAIMERS)
    ]

    results = {}
    barrier = threading.Barrier(len(parties))

    def worker(label, fn):
        barrier.wait()
        code, body = fn()
        return label, code, body

    with ThreadPoolExecutor(max_workers=len(parties)) as ex:
        for label, code, body in ex.map(lambda p: worker(*p), parties):
            results[label] = (code, body)

    task_codes = [v[0] for k, v in results.items() if k.startswith('claim_task')]
    order_codes = [v[0] for k, v in results.items() if k.startswith('claim_order')]
    print(f'[self {idx}] deact_i={results["deact_inspector"][0]} task={task_codes} '
          f'deact_r={results["deact_rectifier"][0]} order={order_codes}')

    # 停用接口必然成功
    check('[self] 停用巡检员成功', results['deact_inspector'][0] == 200, str(results['deact_inspector']))
    check('[self] 停用整改人成功', results['deact_rectifier'][0] == 200, str(results['deact_rectifier']))

    # 领取结果只能是 200 或 409/403，绝不 5xx；且至多一次成功
    check('[self] 任务领取无5xx且成功<=1',
          all(c in (200, 409, 403) for c in task_codes) and sum(c == 200 for c in task_codes) <= 1,
          str(task_codes))
    check('[self] 整改单领取无5xx且成功<=1',
          all(c in (200, 409, 403) for c in order_codes) and sum(c == 200 for c in order_codes) <= 1,
          str(order_codes))
    # 账号停用后，本人若在停用后再领取应得到 403（共享边界生效），用一次滞后请求确认
    c, _ = call('POST', f'/tasks/{tid}/claim/', i_tok)
    check('[self] 停用后本人再领任务被拒(403)', c == 403, f'code={c}')
    c, _ = call('POST', f'/orders/{oid}/claim/', r_tok)
    check('[self] 停用后本人再领整改单被拒(403)', c == 403, f'code={c}')

    # —— 任务终态：不得停在 i_id 名下 ——
    _, t = call('GET', f'/tasks/{tid}/', o_tok)
    task = t['data']
    _, tl = call('GET', f'/tasks/{tid}/timeline/', o_tok)
    t_entries = [e for e in tl['data'] if e['target_type'] == 'task']
    t_actions = [e['action'] for e in t_entries]
    task_claim_200 = sum(c == 200 for c in task_codes)

    check('[self] 任务不停在停用本人名下', task['assignee'] != i_id,
          f"assignee={task['assignee']}({task['assignee_name']}) status={task['status']}")
    if task_claim_200:
        # 本人抢到过：停用必须把它释放（claim 成功后遇停用 → 释放）
        check('[self] 领取成功后遇停用任务被释放到公共池',
              task['assignee'] is None and task['status'] == 'pending',
              f"assignee={task['assignee_name']} status={task['status']}")
        check('[self] 成功领取后必有对应退池交接',
              t_actions.count('claim') >= 1 and 'handoff_pool' in t_actions, str(t_actions))
        # 交接事件必须作用于本人真实持有的资源（无幻象）
        assert_self_handoff_valid(t_entries, '自领巡检员')
    else:
        # 本人没抢到（停用先拿锁）：任务保持公共池待领取，且不得有虚假领取/交接历史
        check('[self] 领取全失败时任务仍在公共池待领取',
              task['assignee'] is None and task['status'] == 'pending',
              f"assignee={task['assignee_name']} status={task['status']}")
        check('[self] 领取全失败不产生claim/handoff历史',
              'claim' not in t_actions and 'handoff_pool' not in t_actions, str(t_actions))

    # 期限保持可回读
    check('[self] 任务期限字段仍可回读', bool(task['due_at']), str(task.get('due_at')))

    # 他人现在必须能领取（待办未卡死）
    c, taken = call('POST', f'/tasks/{tid}/claim/', o_tok)
    check('[self] 释放后其他巡检员可领取', c == 200 and taken['data']['assignee_name'] == '接手巡检员',
          f'{c} {taken.get("data", {})}')

    # —— 整改单终态 ——
    _, od = call('GET', f'/orders/{oid}/', or_tok)
    order = od['data']
    _, tl2 = call('GET', f'/tasks/{tid2}/timeline/', or_tok)
    o_entries = [e for e in tl2['data']
                 if e['target_type'] == 'rectification_order' and e['target_id'] == oid]
    o_actions = [e['action'] for e in o_entries]
    order_claim_200 = sum(c == 200 for c in order_codes)

    check('[self] 整改单不停在停用本人名下', order['assignee'] != r_id,
          f"assignee={order['assignee']}({order['assignee_name']}) status={order['status']}")
    if order_claim_200:
        check('[self] 整改单领取成功后遇停用被释放到公共池',
              order['assignee'] is None and order['status'] == 'pending',
              f"assignee={order['assignee_name']} status={order['status']}")
        check('[self] 整改单成功领取后必有退池交接',
              o_actions.count('claim') >= 1 and 'handoff_pool' in o_actions, str(o_actions))
        assert_self_handoff_valid_order(o_entries, '自领整改人')
    else:
        check('[self] 整改单领取全失败时仍在公共池',
              order['assignee'] is None and order['status'] == 'pending',
              f"assignee={order['assignee_name']} status={order['status']}")
        check('[self] 整改单领取全失败不产生claim/handoff历史',
              'claim' not in o_actions and 'handoff_pool' not in o_actions, str(o_actions))

    check('[self] 整改期限字段仍可回读', bool(order['due_at']), str(order.get('due_at')))
    c, otaken = call('POST', f'/orders/{oid}/claim/', or_tok)
    check('[self] 释放后其他整改人可领取', c == 200 and otaken['data']['assignee_name'] == '接手整改人',
          f'{c} {otaken.get("data", {})}')

    # 挂起升级单：本人曾短暂持有的资源若有挂起升级，交接时一并解除（校验接口不报错即可）
    check('[self] 停用本人无法再登录-巡检', assert_user_disabled(call, insp), '仍可登录')
    check('[self] 停用本人无法再登录-整改', assert_user_disabled(call, rect), '仍可登录')


def assert_self_handoff_valid(entries, self_name):
    """交接事件发生时归属必须正是本人（本人领取后被停用释放）。"""
    owner = None
    problems = []
    for e in entries:
        a = e['action']
        if a in ('publish', 'direct_assign'):
            owner = self_name if a == 'direct_assign' else None
        elif a == 'claim':
            owner = e['actor_name']
        elif a in ('handoff_pool', 'handoff_user'):
            if owner != self_name:
                problems.append(f'{a} 时归属为 {owner!r}，非本人 {self_name!r}')
            owner = None if a == 'handoff_pool' else e['actor_name']
    check('[self] 任务交接事件精确作用于本人持有资源', not problems, '; '.join(problems))


def assert_self_handoff_valid_order(entries, self_name):
    owner = None
    problems = []
    for e in entries:
        a = e['action']
        if a == 'create_from_inspection':
            owner = None
        elif a == 'claim':
            owner = e['actor_name']
        elif a in ('handoff_pool', 'handoff_user'):
            if owner != self_name:
                problems.append(f'{a} 时归属为 {owner!r}，非本人 {self_name!r}')
            owner = None if a == 'handoff_pool' else e['actor_name']
    check('[self] 整改单交接事件精确作用于本人持有资源', not problems, '; '.join(problems))


# --------------------------------------------------------------------------- #
# 跨账号：停用 H 并接管给 T  vs  停用 T
# --------------------------------------------------------------------------- #
def run_cross_round(server, idx):
    """两个停用操作并发：deact(H→T 接管) 与 deact(T)。

    合法终态二选一：
    A) 接管先成功，T 随即被停用 → T 名下刚接管的待办必须被 deact(T) 释放/转出；
    B) deact(T) 先成功 → 接管在锁内发现 T 已停用而失败回滚（409），H 仍启用、
       待办仍在 H 名下（H 未被停用，本就不该动）。
    任意情况下：待办绝不停在已停用账号下；第三个启用账号能立即处理。
    """
    call = make_call(server.base)
    ptoken = login(call, 'wuye')
    bid, aid = pick_building_area(call, ptoken)
    tag = f'c{idx}_{int(time.time() * 1000) % 100000}'

    ih = f'ch_{tag}'   # 被停用持有者（巡检）
    it = f'ct_{tag}'   # 接管人（同时被停用，巡检）
    i3 = f'cx_{tag}'   # 第三个启用巡检
    rh = f'crh_{tag}'  # 被停用持有者（整改）
    rt = f'crt_{tag}'  # 接管整改人（同时被停用）
    r3 = f'crx_{tag}'  # 第三个启用整改

    ih_id = create_user(call, ptoken, ih, '持有者巡检', 'inspector')
    it_id = create_user(call, ptoken, it, '接管人巡检', 'inspector')
    i3_id = create_user(call, ptoken, i3, '第三巡检', 'inspector')
    rh_id = create_user(call, ptoken, rh, '持有者整改', 'rectifier')
    rt_id = create_user(call, ptoken, rt, '接管人整改', 'rectifier')
    r3_id = create_user(call, ptoken, r3, '第三整改', 'rectifier')
    i3_tok = login(call, i3)
    r3_tok = login(call, r3)

    # 巡检任务在 H 名下
    tid = publish(call, ptoken, bid, aid, ih_id, f'跨账号任务-{tag}', ['消防'])
    # 整改单：另一启用巡检提交产生池内整改单，再由整改持有者领取
    submitter = f'cs_{tag}'
    create_user(call, ptoken, submitter, '提交者巡检', 'inspector')
    s_tok = login(call, submitter)
    tid2 = publish(call, ptoken, bid, aid, None, f'跨账号整改来源-{tag}', ['消防', '照明'])
    c, _ = call('POST', f'/tasks/{tid2}/claim/', s_tok)
    assert c == 200
    c, _ = call('POST', f'/tasks/{tid2}/submit/', s_tok, {
        'items': [
            {'name': '消防', 'result': 'issue', 'description': '需整改'},
            {'name': '照明', 'result': 'normal'},
        ]})
    assert c == 200
    _, ods = call('GET', f'/orders/?task={tid2}', s_tok)
    oid = ods['data'][0]['id']
    c, _ = call('POST', f'/orders/{oid}/claim/', login(call, rh))
    assert c == 200

    parties = [
        ('takeover_inspector',
         lambda: call('POST', f'/users/{ih_id}/active/', ptoken,
                      {'is_active': False, 'takeover_user_id': it_id})),
        ('deactivate_target_i',
         lambda: call('POST', f'/users/{it_id}/active/', ptoken, {'is_active': False})),
        ('takeover_rectifier',
         lambda: call('POST', f'/users/{rh_id}/active/', ptoken,
                      {'is_active': False, 'takeover_user_id': rt_id})),
        ('deactivate_target_r',
         lambda: call('POST', f'/users/{rt_id}/active/', ptoken, {'is_active': False})),
    ]

    results = {}
    barrier = threading.Barrier(len(parties))

    def worker(label, fn):
        barrier.wait()
        code, body = fn()
        return label, code, body

    with ThreadPoolExecutor(max_workers=len(parties)) as ex:
        for label, code, body in ex.map(lambda p: worker(*p), parties):
            results[label] = (code, body)

    tk_i = results['takeover_inspector'][0]
    dt_i = results['deactivate_target_i'][0]
    tk_r = results['takeover_rectifier'][0]
    dt_r = results['deactivate_target_r'][0]
    print(f'[cross {idx}] inspector: takeover(H→T)={tk_i} deact(T)={dt_i} | '
          f'rectifier: takeover(H→T)={tk_r} deact(T)={dt_r}')

    def inspect_side(label, res_id, timeline_task_id, target_type, h_id, t_id,
                     x_id, x_tok, h_username, t_username, takeover_code, target_code):
        path = f'/tasks/{res_id}/' if target_type == 'task' else f'/orders/{res_id}/'
        _, td = call('GET', path, x_tok)
        obj = td['data']
        _, tl = call('GET', f'/tasks/{timeline_task_id}/timeline/', x_tok)
        entries = [e for e in tl['data']
                   if e['target_type'] == target_type and e['target_id'] == res_id]
        actions = [e['action'] for e in entries]

        check(f'[cross-{label}] 停用目标T接口成功', target_code == 200, f'code={target_code}')
        check(f'[cross-{label}] 接管接口结果合法(成功200/目标停用409/5xx禁)',
              takeover_code in (200, 409), f'code={takeover_code}')

        # T 最终必停用
        t_disabled = assert_user_disabled(call, t_username)
        check(f'[cross-{label}] 接管人T最终已停用', t_disabled, 'T 仍可登录')
        # H 是否停用取决于接管是否成功：A 成功则 H 停用；B 回滚则 H 仍启用
        h_login = call('POST', '/auth/login/', None, {'username': h_username, 'password': PASSWORD})
        h_active = h_login[0] == 200

        # 不变量：待办绝不停在「已停用」账号名下
        bad = (obj['assignee'] == t_id) or (obj['assignee'] == h_id and not h_active)
        check(f'[cross-{label}] 待办不停在任一已停用账号名下', not bad,
              f"assignee={obj['assignee']}({obj['assignee_name']}) status={obj['status']} "
              f"H_active={h_active} T_disabled={t_disabled}")

        if takeover_code == 200:
            # A：接管成功（H 被停用）→ 随后 T 被停用，待办必须已离开 T 到公共池
            check(f'[cross-{label}] 接管成功后持有者H已停用', not h_active, 'H 仍启用')
            check(f'[cross-{label}] 接管后T被停用，待办离开T到公共池',
                  obj['assignee'] is None,
                  f"assignee={obj['assignee_name']} status={obj['status']}")
            # 历史链：先 handoff_user（到T），再 handoff_pool（T停用释放），且按序
            ui = [i for i, a in enumerate(actions) if a == 'handoff_user']
            pi = [i for i, a in enumerate(actions) if a == 'handoff_pool']
            ordered = bool(ui) and bool(pi) and min(pi) > min(ui)
            check(f'[cross-{label}] 历史含「接管给T→T停用释放」有序两条',
                  ordered, str(actions))
        else:
            # B：接管因目标已停用而失败回滚——H 仍启用、待办原样在 H、无半完成历史
            check(f'[cross-{label}] 接管失败时持有者H未被停用(整体回滚)', h_active, f'login={h_login[0]}')
            check(f'[cross-{label}] 接管失败不写任何handoff历史',
                  'handoff_user' not in actions and 'handoff_pool' not in actions, str(actions))
            check(f'[cross-{label}] 接管失败待办仍在启用的H名下',
                  obj['assignee'] == h_id, f"assignee={obj['assignee_name']}")

        # 成功交接/释放后，第三个启用账号必须能立即处理
        if obj['assignee'] is None:
            claim_path = f'/tasks/{res_id}/claim/' if target_type == 'task' else f'/orders/{res_id}/claim/'
            c, taken = call('POST', claim_path, x_tok)
            check(f'[cross-{label}] 第三启用账号立即领取', c == 200 and taken['data']['assignee'] == x_id,
                  f'{c} {taken.get("error", taken.get("data", {}))}')
        else:
            reassign_path = f'/tasks/{res_id}/reassign/' if target_type == 'task' else f'/orders/{res_id}/reassign/'
            c, data = call('POST', reassign_path, ptoken, {'user_id': x_id})
            check(f'[cross-{label}] 可立即重新分派给第三启用账号',
                  c == 200 and data['data']['assignee'] == x_id, f'{c} {data.get("error")}')

        check(f'[cross-{label}] 期限字段可回读', bool(obj['due_at']), '')

    inspect_side('task', tid, tid, 'task', ih_id, it_id, i3_id, i3_tok, ih, it, tk_i, dt_i)
    inspect_side('order', oid, tid2, 'rectification_order', rh_id, rt_id, r3_id, r3_tok,
                 rh, rt, tk_r, dt_r)


# --------------------------------------------------------------------------- #
# 并发场景
# --------------------------------------------------------------------------- #
def run_round(server, idx, kind):
    call = make_call(server.base)
    ptoken = login(call, 'wuye')
    bid, aid = pick_building_area(call, ptoken)
    tag = f'r{idx}_{kind}_{int(time.time() * 1000) % 100000}'

    # 本轮专属人员（停用只影响本轮资源）
    insp_holder = f'ih_{tag}'
    insp_rival = f'ir_{tag}'
    rect_holder = f'rh_{tag}'
    rect_rival = f'rr_{tag}'
    ih_id = create_user(call, ptoken, insp_holder, '巡检持有者', 'inspector')
    ir_id = create_user(call, ptoken, insp_rival, '巡检竞争者', 'inspector')
    rh_id = create_user(call, ptoken, rect_holder, '整改持有者', 'rectifier')
    rr_id = create_user(call, ptoken, rect_rival, '整改竞争者', 'rectifier')
    ih_tok = login(call, insp_holder)
    ir_tok = login(call, insp_rival)
    rh_tok = login(call, rect_holder)
    rr_tok = login(call, rect_rival)

    if kind == 'claimed':
        # 纯巡检中任务：领取 vs 停用
        tid = publish(call, ptoken, bid, aid, ih_id, f'并发-{tag}', ['消防通道'])
        order_id = None
    else:
        # 已提交异常：任务待复验 + 整改单处理中，同时并发四组动作
        tid = publish(call, ptoken, bid, aid, ih_id, f'并发-{tag}', ['消防通道', '照明'])
        code, data = call('POST', f'/tasks/{tid}/submit/', ih_tok, {
            'items': [
                {'name': '消防通道', 'result': 'issue', 'description': '通道被占用'},
                {'name': '照明', 'result': 'normal'},
            ],
        })
        assert code == 200, data
        _, ods = call('GET', f'/orders/?task={tid}', ir_tok)
        order_id = ods['data'][0]['id']
        code, data = call('POST', f'/orders/{order_id}/claim/', rh_tok)
        assert code == 200, data

    # 组装并发动作
    parties = []

    def deactivate(user_id):
        return lambda: call('POST', f'/users/{user_id}/active/', ptoken, {'is_active': False})

    parties.append(('deact_inspector', deactivate(ih_id)))
    parties += [
        (f'claim_task_{i}', (lambda tid=tid: call('POST', f'/tasks/{tid}/claim/', ir_tok)))
        for i in range(CLAIMERS)
    ]
    if kind == 'issue':
        parties.append(('deact_rectifier', deactivate(rh_id)))
        parties += [
            (f'claim_order_{i}', (lambda oid=order_id: call('POST', f'/orders/{oid}/claim/', rr_tok)))
            for i in range(CLAIMERS)
        ]

    # 收集 HTTP 状态码
    results = {}
    barrier = threading.Barrier(len(parties))

    def worker(label, fn):
        barrier.wait()
        code, _ = fn()
        return label, code

    with ThreadPoolExecutor(max_workers=len(parties)) as ex:
        for label, code in ex.map(lambda p: worker(*p), parties):
            results[label] = code

    task_claim_codes = [v for k, v in results.items() if k.startswith('claim_task')]
    order_claim_codes = [v for k, v in results.items() if k.startswith('claim_order')]
    deact_insp = results.get('deact_inspector')
    deact_rect = results.get('deact_rectifier')

    print(f'[round {idx}:{kind}] deact_insp={deact_insp} task_claims={task_claim_codes}'
          + (f' deact_rect={deact_rect} order_claims={order_claim_codes}' if kind == 'issue' else ''))

    check(f'[{kind}] 停用巡检员接口成功(200)', deact_insp == 200, f'code={deact_insp}')
    _, task_held_by_rival = assert_task_consistency(
        call, ir_tok, tid, ih_id, ir_id, task_claim_codes, kind, '巡检持有者')
    check(f'[{kind}] 停用巡检员无法再登录', assert_user_disabled(call, insp_holder), '仍可登录')

    order_held_by_rival = None
    if kind == 'issue':
        check(f'[{kind}] 停用整改人接口成功(200)', deact_rect == 200, f'code={deact_rect}')
        order = {'id': order_id, 'task': tid}
        order_held_by_rival = assert_order_consistency(
            call, rr_tok, order, order_claim_codes, rh_id, rr_id, kind, '整改持有者')
        check(f'[{kind}] 停用整改人无法再登录', assert_user_disabled(call, rect_holder), '仍可登录')

    return {'kind': kind, 'task_held_by_rival': task_held_by_rival,
            'order_held_by_rival': order_held_by_rival}


def main():
    server = RealServer()
    summary = []
    self_count = 0
    cross_count = 0
    try:
        server.start()
        for i in range(1, ROUNDS + 1):
            summary.append(run_round(server, i, 'claimed'))
            summary.append(run_round(server, i, 'issue'))
        # 同一人：本人领取 vs 停用本人
        for i in range(1, ROUNDS + 1):
            run_self_round(server, i)
            self_count += 1
        # 跨账号：停用 H 并接管给 T，与停用 T 同时发生
        for i in range(1, ROUNDS + 1):
            run_cross_round(server, i)
            cross_count += 1
    finally:
        server.stop()

    print('\n================ 并发结果分布（仅记录，不依赖其出现） ================')
    for kind in ('claimed', 'issue'):
        rows = [s for s in summary if s['kind'] == kind]
        tw = sum(1 for s in rows if s['task_held_by_rival'])
        print(f'  {kind}: 共 {len(rows)} 轮，任务最终归竞争者 {tw} 轮，在公共池 {len(rows) - tw} 轮')
        if kind == 'issue':
            ow = sum(1 for s in rows if s['order_held_by_rival'])
            print(f'  issue 整改单: 归竞争者 {ow} 轮，在公共池 {len(rows) - ow} 轮')
    print(f'  同一人领取-停用竞争场景：{self_count} 轮')
    print(f'  跨账号接管-停用竞争场景：{cross_count} 轮')

    total = ROUNDS * 2 + self_count + cross_count
    print(f'\n================ {total} 个并发场景，失败 {len(failures)} 个 ================')
    if failures:
        print('\n'.join('- ' + f for f in failures[:30]))
        return 1
    print('全部一致：最终归属唯一、无重复成功、失败方未改动数据、历史完整、停用者不可登录。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
