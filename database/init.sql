-- ============================================================
-- AI Opinion Analytics — MySQL 数据库初始化脚本
-- 用法: mysql -u root -p < init.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS opinion_analytics
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE opinion_analytics;

-- ============================================================
-- 1. users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(36)  PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    email           VARCHAR(128) NULL UNIQUE,
    avatar_url      VARCHAR(512) NULL,
    role            ENUM('admin','analyst','viewer') NOT NULL DEFAULT 'analyst',
    api_key         VARCHAR(256) NULL,
    credits         INT          NOT NULL DEFAULT 0,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at   DATETIME     NULL,
    remember_token  VARCHAR(256) NULL,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. videos
-- ============================================================
CREATE TABLE IF NOT EXISTS videos (
    id                VARCHAR(36)  PRIMARY KEY,
    platform          ENUM('bilibili','douyin') NOT NULL,
    platform_video_id VARCHAR(64)  NOT NULL,
    title             VARCHAR(512) NOT NULL,
    description       TEXT         NULL,
    cover_url         VARCHAR(512) NULL,
    uploader_name     VARCHAR(128) NULL,
    uploader_id       VARCHAR(64)  NULL,
    url               VARCHAR(512) NOT NULL,
    publish_time      DATETIME     NULL,
    duration_seconds  INT          NULL,
    comment_count     INT          NOT NULL DEFAULT 0,
    view_count        INT          NULL,
    like_count        INT          NULL,
    analysis_status   ENUM('pending','analyzing','analyzed','tracking') NOT NULL DEFAULT 'pending',
    last_analysis_at  DATETIME     NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_videos_platform (platform),
    INDEX idx_videos_analysis_status (analysis_status),
    INDEX idx_videos_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. analysis_tasks
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id                      VARCHAR(36) PRIMARY KEY,
    user_id                 VARCHAR(36) NOT NULL,
    video_id                VARCHAR(36) NOT NULL,
    platform                VARCHAR(16) NOT NULL,
    mode                    ENUM('normal','tracking') NOT NULL,
    comment_limit           INT         NOT NULL DEFAULT 500 COMMENT '0=全部',
    time_range              ENUM('7d','30d','all') NOT NULL DEFAULT '7d',
    language_filter         ENUM('zh','en','all') NOT NULL DEFAULT 'zh',
    status                  ENUM('queued','collecting','cleaning','embedding','clustering','topic_gen','summarizing','completed','failed') NOT NULL DEFAULT 'queued',
    progress_pct            INT         NOT NULL DEFAULT 0,
    total_comments_processed INT        NOT NULL DEFAULT 0,
    topic_count             INT         NOT NULL DEFAULT 0,
    error_message           TEXT        NULL,
    started_at              DATETIME    NULL,
    completed_at            DATETIME    NULL,
    duration_ms             INT         NULL,
    created_at              DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tasks_user_id (user_id),
    INDEX idx_tasks_video_id (video_id),
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_created_at (created_at),
    CONSTRAINT fk_tasks_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_tasks_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. topics（必须在 comments 之前创建）
-- ============================================================
CREATE TABLE IF NOT EXISTS topics (
    id                          VARCHAR(36)  PRIMARY KEY,
    task_id                     VARCHAR(36)  NOT NULL,
    video_id                    VARCHAR(36)  NOT NULL,
    name                        VARCHAR(128) NOT NULL,
    comment_count               INT          NOT NULL DEFAULT 0,
    percentage                  FLOAT        NOT NULL DEFAULT 0.0,
    keywords_json               TEXT         NULL COMMENT 'JSON array ["kw1","kw2",...]',
    representative_comment_ids_json TEXT      NULL COMMENT 'JSON array of comment UUIDs',
    ai_summary                  TEXT         NULL,
    sentiment_distribution_json TEXT         NULL COMMENT '{"positive":N,"negative":N,"neutral":N}',
    created_at                  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_topics_task_id (task_id),
    INDEX idx_topics_video_id (video_id),
    INDEX idx_topics_name (name),
    CONSTRAINT fk_topics_task   FOREIGN KEY (task_id)  REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_topics_video  FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. comments（依赖 videos + topics）
-- ============================================================
CREATE TABLE IF NOT EXISTS comments (
    id                  VARCHAR(36)  PRIMARY KEY,
    video_id            VARCHAR(36)  NOT NULL,
    platform_comment_id VARCHAR(64)  NOT NULL,
    content             TEXT         NOT NULL,
    author_name         VARCHAR(128) NULL,
    author_avatar       VARCHAR(512) NULL,
    like_count          INT          NOT NULL DEFAULT 0,
    reply_count         INT          NOT NULL DEFAULT 0,
    publish_time        DATETIME     NULL,
    language            VARCHAR(10)  NULL,
    embedding_json      MEDIUMTEXT   NULL COMMENT 'JSON array of float values',
    sentiment           ENUM('positive','negative','neutral') NULL,
    sentiment_score     FLOAT        NULL,
    topic_id            VARCHAR(36)  NULL,
    is_cleaned          TINYINT(1)   NOT NULL DEFAULT 0,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comments_video_id (video_id),
    INDEX idx_comments_topic_id (topic_id),
    INDEX idx_comments_sentiment (sentiment),
    INDEX idx_comments_publish_time (publish_time),
    INDEX idx_comments_platform_cid (platform_comment_id),
    FULLTEXT INDEX ft_comment_content (content) WITH PARSER ngram,
    CONSTRAINT fk_comments_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_topic FOREIGN KEY (topic_id)  REFERENCES topics(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. sentiments
-- ============================================================
CREATE TABLE IF NOT EXISTS sentiments (
    id          VARCHAR(36)  PRIMARY KEY,
    comment_id  VARCHAR(36)  NOT NULL,
    task_id     VARCHAR(36)  NOT NULL,
    aspect      VARCHAR(64)  NOT NULL COMMENT '属性维度，如价格/性能/续航',
    sentiment   VARCHAR(16)  NOT NULL COMMENT 'positive / negative / neutral',
    score       FLOAT        NOT NULL DEFAULT 0.0 COMMENT '0-5 情感强度',
    confidence  FLOAT        NULL     COMMENT '0-1 置信度',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sentiments_comment_id (comment_id),
    INDEX idx_sentiments_task_id (task_id),
    INDEX idx_sentiments_aspect (aspect),
    CONSTRAINT fk_sentiments_comment FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    CONSTRAINT fk_sentiments_task    FOREIGN KEY (task_id)    REFERENCES analysis_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 7. tracking_tasks
-- ============================================================
CREATE TABLE IF NOT EXISTS tracking_tasks (
    id                      VARCHAR(36) PRIMARY KEY,
    analysis_task_id        VARCHAR(36) NOT NULL,
    video_id                VARCHAR(36) NOT NULL,
    user_id                 VARCHAR(36) NOT NULL,
    status                  ENUM('active','paused','stopped','exhausted') NOT NULL DEFAULT 'active',
    poll_interval_seconds   INT         NOT NULL DEFAULT 60,
    new_comments_since_start INT        NOT NULL DEFAULT 0,
    credits_consumed        FLOAT       NOT NULL DEFAULT 0.0,
    credits_rate_per_hour   INT         NOT NULL DEFAULT 100,
    started_at              DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stopped_at              DATETIME    NULL,
    last_poll_at            DATETIME    NULL,
    last_comment_id         VARCHAR(64) NULL,
    INDEX idx_tracking_task_id (analysis_task_id),
    INDEX idx_tracking_video_id (video_id),
    INDEX idx_tracking_user_id (user_id),
    INDEX idx_tracking_status (status),
    CONSTRAINT fk_tracking_analysis_task FOREIGN KEY (analysis_task_id) REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_tracking_video         FOREIGN KEY (video_id)         REFERENCES videos(id) ON DELETE CASCADE,
    CONSTRAINT fk_tracking_user          FOREIGN KEY (user_id)          REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 8. credits
-- ============================================================
CREATE TABLE IF NOT EXISTS credits (
    id               VARCHAR(36)  PRIMARY KEY,
    user_id          VARCHAR(36)  NOT NULL,
    balance_after    INT          NOT NULL COMMENT '交易后余额',
    transaction_type ENUM('purchase','consume','refund','gift') NOT NULL,
    amount           INT          NOT NULL COMMENT '正数=充值 负数=消费',
    task_id          VARCHAR(36)  NULL,
    description      VARCHAR(512) NULL,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_credits_user_id (user_id),
    INDEX idx_credits_created_at (created_at),
    INDEX idx_credits_task_id (task_id),
    CONSTRAINT fk_credits_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 9. user_settings
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id                     VARCHAR(36) PRIMARY KEY,
    user_id                VARCHAR(36) NOT NULL UNIQUE,
    default_comment_count  INT         NOT NULL DEFAULT 500,
    auto_generate_summary  TINYINT(1)  NOT NULL DEFAULT 1,
    realtime_animation     TINYINT(1)  NOT NULL DEFAULT 1,
    notify_on_complete     TINYINT(1)  NOT NULL DEFAULT 1,
    notify_on_anomaly      TINYINT(1)  NOT NULL DEFAULT 1,
    created_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_settings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 10. analysis_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_logs (
    id           VARCHAR(36) PRIMARY KEY,
    task_id      VARCHAR(36) NOT NULL,
    log_level    VARCHAR(16) NOT NULL DEFAULT 'info' COMMENT 'info / success / warn / error',
    stage        VARCHAR(32) NULL     COMMENT 'collecting / cleaning / embedding / clustering / topic_gen / summarizing',
    message      TEXT        NOT NULL,
    metadata_json TEXT       NULL,
    created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_logs_task_id (task_id),
    INDEX idx_logs_level (log_level),
    INDEX idx_logs_created_at (created_at),
    CONSTRAINT fk_logs_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 初始化数据
-- ============================================================

-- 管理员账户 (用户名: admin, 密码: admin123)
INSERT INTO users (id, username, password_hash, email, role, credits, created_at) VALUES
('00000000-0000-0000-0000-000000000001', 'admin',
 '$2b$12$zU6kzqY22kPq1DPAvEHFvezocQoU37Z2g8UBchbH5L0Kj46kMTvN2',
 'admin@opinion.ai', 'admin', 5000, NOW());

-- 默认用户设置 (首次登录自动创建，这里为 admin 预创建)
INSERT INTO user_settings (id, user_id) VALUES
('00000000-0000-0000-0000-000000000100', '00000000-0000-0000-0000-000000000001');

-- ============================================================
-- 验证
-- ============================================================
SELECT '=== 数据库初始化完成 ===' AS message;

SELECT TABLE_NAME AS '表名',
       TABLE_ROWS AS '行数',
       ROUND(DATA_LENGTH/1024, 2) AS '数据大小(KB)'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'opinion_analytics'
ORDER BY TABLE_NAME;
