-- 巡检整改闭环系统：数据库由 Django migrations 自动建表（见 backend/entrypoint.sh）。
-- 此处仅做数据库级初始化，确保扩展可用，不手工创建业务表，避免与迁移不一致。
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
