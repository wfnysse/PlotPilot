#!/usr/bin/env python3
"""
从章节内容中提取标题并更新title字段
"""
import sys
import json
import re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

CHAPTERS_DIR = Path("data/novels/novel-1775066530753/chapters")

def extract_title_from_content(content):
    """从content中提取标题"""
    if not content:
        return None

    # 查找第一行的Markdown标题
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            # 移除#号和空格
            title = re.sub(r'^#+\s*', '', line)
            return title

    return None

def update_chapter_titles():
    """更新所有章节的标题"""
    updated_count = 0

    for chapter_file in sorted(CHAPTERS_DIR.glob("*.json")):
        try:
            # 读取章节文件
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)

            # 提取标题
            content = chapter_data.get('content', '')
            extracted_title = extract_title_from_content(content)

            if extracted_title and extracted_title != chapter_data.get('title'):
                old_title = chapter_data.get('title')
                chapter_data['title'] = extracted_title

                # 写回文件
                with open(chapter_file, 'w', encoding='utf-8') as f:
                    json.dump(chapter_data, f, ensure_ascii=False, indent=2)

                print(f"✓ {chapter_file.name}: \"{old_title}\" → \"{extracted_title}\"")
                updated_count += 1
            else:
                print(f"- {chapter_file.name}: 无需更新")

        except Exception as e:
            print(f"✗ {chapter_file.name}: 错误 - {e}")

    print(f"\n总计更新: {updated_count} 个章节")

if __name__ == "__main__":
    print("开始更新章节标题...")
    print("=" * 60)
    update_chapter_titles()
    print("=" * 60)
    print("完成！")
