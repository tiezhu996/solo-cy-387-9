"""业务错误码与提示统一维护。code 为对外稳定错误码，message 为默认中文提示。"""

ERRORS = {
    'VALIDATION_ERROR': '参数校验失败',
    'UNAUTHORIZED': '未登录或登录已失效',
    'PERMISSION_DENIED': '没有执行该操作的权限',
    'USER_DISABLED': '账号已停用，请联系管理员',
    'BUILDING_NOT_FOUND': '楼栋不存在',
    'AREA_NOT_FOUND': '巡检区域不存在',
    'TASK_NOT_FOUND': '巡检任务不存在',
    'ORDER_NOT_FOUND': '整改单不存在',
    'TASK_NOT_CLAIMABLE': '任务已被领取或已关闭，无法重复领取',
    'TASK_NOT_SUBMITTABLE': '当前任务状态不允许提交巡检结果',
    'NOT_TASK_OWNER': '只有领取该任务的巡检员可以操作',
    'ORDER_NOT_CLAIMABLE': '整改单已被领取或已关闭，无法重复领取',
    'ORDER_NOT_PROCESSING': '当前整改单状态不允许提交处理结果',
    'ORDER_NOT_RECHECKABLE': '整改单尚未提交处理结果，无法复验',
    'NOT_ORDER_OWNER': '只有当前整改负责人可以提交处理结果',
    'TASK_HAS_OPEN_ORDERS': '仍有整改单未复验通过，任务不能关闭',
    'TASK_NOT_RESCHEDULABLE': '已关闭的任务不能改期',
    'TASK_NOT_REASSIGNABLE': '已关闭的任务不能重新分派',
    'USER_NOT_FOUND': '人员不存在',
    'ROLE_MISMATCH': '所选人员角色与操作不匹配',
    'REQUIRES_RECTIFIER': '必须指定或由整改人领取整改单',
    'ISSUE_NEEDS_DESCRIPTION': '异常检查项必须填写问题描述',
}


class BusinessError(Exception):
    """业务异常：携带稳定错误码与 HTTP 状态码，由统一异常处理器转换。"""

    def __init__(self, code: str, status_code: int = 400, message: str | None = None):
        self.code = code
        self.status_code = status_code
        self.message = message or ERRORS.get(code, code)
        super().__init__(self.message)
