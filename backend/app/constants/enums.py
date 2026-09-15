"""统一维护的业务枚举常量。"""

# 用户角色
ROLE_PROPERTY = 'property'      # 物业管理员：发布任务、改期、重新分派、停用人员
ROLE_INSPECTOR = 'inspector'    # 巡检员：领取、提交结果、复验
ROLE_RECTIFIER = 'rectifier'    # 整改人：领取整改单、提交处理结果
ROLE_SUPERVISOR = 'supervisor'  # 主管：处理超期升级

ROLE_CHOICES = (
    (ROLE_PROPERTY, '物业管理员'),
    (ROLE_INSPECTOR, '巡检员'),
    (ROLE_RECTIFIER, '整改人'),
    (ROLE_SUPERVISOR, '主管'),
)
ROLE_LABELS = dict(ROLE_CHOICES)

# 巡检周期
PERIOD_DAILY = 'daily'
PERIOD_WEEKLY = 'weekly'
PERIOD_MONTHLY = 'monthly'
PERIOD_CHOICES = (
    (PERIOD_DAILY, '每日'),
    (PERIOD_WEEKLY, '每周'),
    (PERIOD_MONTHLY, '每月'),
)
PERIOD_LABELS = dict(PERIOD_CHOICES)

# 巡检任务状态
TASK_PENDING = 'pending'        # 待领取
TASK_CLAIMED = 'claimed'        # 已领取，巡检中
TASK_SUBMITTED = 'submitted'    # 已提交（含异常），等待整改
TASK_RETURNED = 'returned'      # 复验驳回，重新整改
TASK_DONE = 'done'              # 闭环关闭
TASK_CHOICES = (
    (TASK_PENDING, '待领取'),
    (TASK_CLAIMED, '巡检中'),
    (TASK_SUBMITTED, '待整改'),
    (TASK_RETURNED, '复验驳回'),
    (TASK_DONE, '已关闭'),
)
TASK_LABELS = dict(TASK_CHOICES)

# 检查项结果
RESULT_NORMAL = 'normal'
RESULT_ISSUE = 'issue'
RESULT_CHOICES = (
    (RESULT_NORMAL, '正常'),
    (RESULT_ISSUE, '异常'),
)
RESULT_LABELS = dict(RESULT_CHOICES)

# 整改单状态
ORDER_PENDING = 'pending'       # 待领取（或待指定整改人处理）
ORDER_PROCESSING = 'processing'  # 整改中
ORDER_SUBMITTED = 'submitted'   # 已提交处理结果，待复验
ORDER_RETURNED = 'returned'     # 复验驳回，重新整改
ORDER_VERIFIED = 'verified'     # 复验通过
ORDER_CLOSED = 'closed'         # 已关闭（随任务关闭）
ORDER_CHOICES = (
    (ORDER_PENDING, '待整改'),
    (ORDER_PROCESSING, '整改中'),
    (ORDER_SUBMITTED, '待复验'),
    (ORDER_RETURNED, '复验驳回'),
    (ORDER_VERIFIED, '复验通过'),
    (ORDER_CLOSED, '已关闭'),
)
ORDER_LABELS = dict(ORDER_CHOICES)

# 整改来源
SOURCE_INSPECTION = 'inspection'   # 巡检异常
SOURCE_RECHECK = 'recheck'         # 复验驳回后重新整改
SOURCE_CHOICES = (
    (SOURCE_INSPECTION, '巡检提交'),
    (SOURCE_RECHECK, '复验驳回'),
)
SOURCE_LABELS = dict(SOURCE_CHOICES)

# 升级级别
ESCALATION_SUPERVISOR = 'supervisor'
ESCALATION_CHOICES = (
    (ESCALATION_SUPERVISOR, '主管'),
)
ESCALATION_LABELS = dict(ESCALATION_CHOICES)

# 升级对象类型
TARGET_TASK = 'task'
TARGET_ORDER = 'rectification_order'
TARGET_CHOICES = (
    (TARGET_TASK, '巡检任务'),
    (TARGET_ORDER, '整改单'),
)

# 通用严重程度
SEVERITY_CHOICES = (
    ('low', '一般'),
    ('medium', '较重'),
    ('high', '严重'),
)
SEVERITY_LABELS = dict(SEVERITY_CHOICES)
