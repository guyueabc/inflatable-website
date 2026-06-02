# 备份规则

## 使用方式

每次修改网站项目前，在项目根目录手动运行：

```bash
python backup.py
```

脚本会自动创建新版本备份，不会删除任何旧版本。

## 版本命名规则

格式：`v{N}_{YYYYMMDD}`

- N：自动递增的版本号（v1, v2, v3...）
- YYYYMMDD：备份日期

示例：`v1_20260526`

所有备份存放在 `backups/` 目录下。

## 备份内容

| 类别 | 路径 | 说明 |
|------|------|------|
| 主程序 | `app.py` | Flask 应用入口 |
| 配置 | `config.py` | 应用配置 |
| 文档 | `DEPLOY.md` | 部署说明 |
| HTML 模板 | `templates/*.html` | 全部前端页面模板 |
| 样式 | `static/css/style.css` | 网站样式表 |

## 不备份的内容

- `data.db` — SQLite 数据库文件（用户数据，体积大）
- `uploads/` — 用户上传文件目录
- `backups/` — 备份目录自身（避免嵌套）
- `__pycache__/` — Python 字节码缓存