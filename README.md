# 公共区域巡检与整改闭环系统（PatrolLoop）

```bash
cp .env.example .env
docker compose up -d --build
```

面向物业的公共区域巡检与整改闭环平台：物业按楼栋、区域和周期发布巡检任务，巡检员领取后提交现场结果与照片；发现问题自动生成整改单并保留来源，整改人处理后由巡检员复验，复验通过才能关闭；超期未处理自动升级给主管。全程状态留痕，刷新或重启后完整闭环仍可追溯。

- 访问地址：http://localhost:18407
- 后端直连：http://localhost:19407
- 演示账号密码统一为：`demo123456`（登录页可点击快捷登录）

| 角色 | 登录名 | 主要职责 |
| --- | --- | --- |
| 物业管理员 | `wuye` | 发布任务、改期、重新分派、停用人员、处置组织架构 |
| 巡检员 | `xunjian1` / `xunjian2` | 领取任务、提交现场结果与照片、复验整改单、关闭闭环 |
| 整改人 | `zhenggai1` / `zhenggai2` | 领取整改单、提交处理结果与照片 |
| 主管 | `zhuguan` | 查看并处置超期升级单 |

## 项目主要功能

- **任务发布**：按楼栋、巡检区域、周期（每日/每周/每月）发布，配置检查项清单、计划时间与巡检期限，可直接指派或放入公共待领池。
- **并发安全领取**：重复领取或多人并发领取，数据库条件更新保证**只有一人成功**，其余得到明确冲突提示，绝不出现两人同时处理。
- **现场巡检**：逐项填报「正常/异常」，异常必须填写问题描述并上传照片；提交后自动生成整改单，**完整保留问题来源**（来源任务、检查项、问题照片快照）。
- **整改与复验**：整改人领取并提交处理结果；巡检员复验通过或驳回，驳回自动进入下一轮整改，每轮记录都保留。
- **闭环关闭**：全部整改单复验通过后任务才能关闭，整改单随任务一并关闭；仍有未完成整改单时禁止关闭。
- **改期 / 重新分派 / 停用**：改期同步计划与期限；重新分派即时切换待办归属，原负责人立即失效；停用人员无法登录，并在**同一事务**内把其名下未完成的巡检任务/整改单退回公共池或交给指定接管人，挂起升级单一并解除，待办绝不卡死；重新启用不自动拿回已释放待办，历史记录始终保留。
- **超期升级**：调度服务周期扫描超期任务/整改单，幂等生成升级单推送给主管处置；闭环后自动解除。
- **完整状态历史**：任务与每张整改单的每次流转都写入只增审计表，任务详情页合并为一条时间线，**浏览器刷新、服务重启后仍可完整回放**。

## 快速启动方式（Docker Compose）

首次启动前执行：

```bash
cp .env.example .env
docker compose up -d --build
```

启动包含四个服务：

| 服务 | 容器名 | 说明 |
| --- | --- | --- |
| db | patrolloop-db | PostgreSQL 16，带健康检查 |
| backend | patrolloop-backend | Django/DRF API，启动时自动迁移并初始化演示数据 |
| scheduler | patrolloop-scheduler | 周期执行超期扫描（默认每 600 秒） |
| frontend | patrolloop-frontend | Nginx 托管前端并反向代理 `/api`、`/media` |

停止与清理：

```bash
docker compose down          # 停止（保留数据卷）
docker compose down -v       # 停止并删除数据卷
```

> 任意目录名（含中文目录名）下均可启动：Compose 使用顶层固定 `name: patrolloop` 与命名卷，不依赖所在目录。

## 本地开发方式

后端（默认使用 SQLite，零外部依赖；也可用 `DATABASE_URL` 指向 PostgreSQL）：

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_demo     # 初始化演示账号与任务（幂等）
python manage.py runserver 0.0.0.0:8000
# 手动触发一次超期扫描：
python manage.py scan_overdue
```

前端：

```bash
cd frontend
npm install
npm run dev        # http://localhost:18407 ，/api 代理到 http://localhost:19407
```

端到端 + 并发自检（需要先在 8000 端口跑起后端并完成迁移/种子）：

```bash
cd backend
PORT=8000 python3 scripts/e2e_check.py       # 完整闭环 + 并发领取/复验/权限
PORT=8000 python3 scripts/test_handoff.py    # 停用交接/接管/并发停用-领取
```

覆盖：多线程并发领取任务/整改单仅一人成功、停用与领取同时竞争只有一个结果、完整异常→整改→驳回→复验→关闭闭环、改期/重新分派/停用归属与可领取状态同步、挂起升级单一并解除、历史不丢失、重新启用不拿回待办、角色权限。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Element Plus |
| 后端 | Python、Django 5、Django REST Framework |
| 数据库 | PostgreSQL 16（本地开发可回落 SQLite + WAL） |
| 认证 | 数据库持久化 Token（刷新/重启登录态不丢失） |
| 图片存储 | 后端本地 `media/` 目录，Nginx 反代 `/media` |
| 部署 | Docker Compose、Gunicorn、Nginx |
| 定时任务 | 独立 scheduler 容器运行 `scan_overdue` 管理命令 |

## 项目目录结构

```text
.
├── docker-compose.yml
├── .env.example
├── README.md
├── backend
│   ├── Dockerfile
│   ├── entrypoint.sh            # 迁移 + 种子 + 启动 / 超期调度
│   ├── requirements.txt
│   ├── manage.py
│   ├── database
│   │   └── init.sql
│   ├── scripts
│   │   └── e2e_check.py         # 端到端 + 并发自检
│   └── app
│       ├── settings.py
│       ├── urls.py
│       ├── api_media.py         # 照片上传
│       ├── constants            # 枚举、错误码统一维护
│       ├── utils                # 认证、权限、统一响应/异常、日志
│       ├── middleware
│       └── apps
│           ├── users            # 账号、登录令牌、人员停用
│           ├── organization     # 楼栋、巡检区域
│           ├── inspection       # 巡检任务、提交、领取、改期、分派
│           ├── rectification    # 整改单、处理记录、复验、关闭
│           ├── escalation       # 超期升级单与扫描
│           └── audit            # 只增状态历史（闭环时间线来源）
└── frontend
    ├── Dockerfile               # 多阶段构建
    ├── nginx.conf               # SPA + /api + /media 反代
    └── src
        ├── api                  # 请求封装与接口聚合
        ├── stores               # 登录态
        ├── router
        ├── types
        ├── components           # 任务表、整改单卡片、时间线、上传等
        └── views                # 登录、工作台、任务详情、人员、升级台等
```

## 关键设计：并发领取与状态一致性

- 领取（任务与整改单）在一个数据库事务内以**条件 UPDATE** 作为首语句：
  `UPDATE ... SET assignee=? WHERE id=? AND assignee IS NULL AND status='pending'`。
  受影响行数为 1 才领取成功；并发下数据库行锁（PostgreSQL）或写事务排队（SQLite WAL）保证只有一人成功，其余返回 `409 TASK_NOT_CLAIMABLE` / `ORDER_NOT_CLAIMABLE`。
- 所有状态流转（发布、领取、提交、生成整改单、整改、复验、关闭、改期、分派、停用、升级）都在事务内完成，并同步写入 `audit_status_history`，历史只增不改，因此任何重新分派或人员停用都不会让原记录丢失。
- 关闭是强约束：存在未复验通过的整改单时返回 `409 TASK_HAS_OPEN_ORDERS`。

## 环境变量说明

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| COMPOSE_PROJECT_NAME | Compose 项目名 | patrolloop |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | 数据库名/用户/密码 | patrolloop / patrolloop / patrolloop_pass |
| DJANGO_SECRET_KEY | Django 密钥，生产环境务必修改 | 内置开发值 |
| DJANGO_DEBUG | 是否开启调试 | false |
| SCAN_INTERVAL_SECONDS | 超期扫描间隔（秒） | 600 |
| DATABASE_URL | 后端数据库连接串（本地开发用） | 本地 SQLite |
| MEDIA_ROOT | 照片存储目录（容器内） | /app/media |

## Docker 部署说明

- Compose 顶层声明 `name: patrolloop`，容器名带 `patrolloop-` 前缀。
- PostgreSQL 数据与媒体文件分别使用命名卷 `patrolloop_pg_data`、`patrolloop_media` 持久化。
- 前端 Nginx 将 `/api/` 代理到 `backend:8000`，将 `/media/` 代理到 `backend:8000/media/`，并对 SPA 路由做回退。
- 数据库与后端均配置了 `healthcheck`，调度服务在后端健康后启动。
- 端口：前端 `18407:80`，后端 `19407:8000`。

## License

MIT
