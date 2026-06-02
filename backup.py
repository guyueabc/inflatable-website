"""自动备份脚本 - 每次修改前运行以创建带版本号的源码备份"""

import os
import shutil
import re
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")

# 需要备份的文件和目录
BACKUP_ITEMS = [
    "app.py",
    "config.py",
    "DEPLOY.md",
    ("templates", "*.html"),
    ("static/css", "style.css"),
]


def get_next_version():
    """扫描 backups/ 目录，返回下一个版本号"""
    if not os.path.isdir(BACKUP_DIR):
        return 1

    pattern = re.compile(r"^v(\d+)_\d{8}$")
    max_v = 0
    for name in os.listdir(BACKUP_DIR):
        m = pattern.match(name)
        if m:
            max_v = max(max_v, int(m.group(1)))
    return max_v + 1


def create_backup():
    version = get_next_version()
    date_str = date.today().strftime("%Y%m%d")
    backup_name = f"v{version}_{date_str}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    os.makedirs(backup_path, exist_ok=True)

    for item in BACKUP_ITEMS:
        if isinstance(item, tuple):
            src_dir, file_pattern = item
            src_full = os.path.join(PROJECT_ROOT, src_dir)
            dst_full = os.path.join(backup_path, src_dir)
            if not os.path.isdir(src_full):
                print(f"  [跳过] 目录不存在: {src_dir}")
                continue
            os.makedirs(dst_full, exist_ok=True)

            import glob
            pattern_path = os.path.join(src_full, file_pattern)
            for f in glob.glob(pattern_path):
                shutil.copy2(f, os.path.join(dst_full, os.path.basename(f)))
                print(f"  [复制] {os.path.relpath(f, PROJECT_ROOT)}")
        else:
            src_file = os.path.join(PROJECT_ROOT, item)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(backup_path, item))
                print(f"  [复制] {item}")
            else:
                print(f"  [跳过] 文件不存在: {item}")

    print(f"\n备份完成: {backup_path}")
    return backup_path


if __name__ == "__main__":
    create_backup()