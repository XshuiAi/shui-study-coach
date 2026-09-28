#!/usr/bin/env python3
"""stdin quiz JSON -> stdout HTML. No output path and no file mutations."""
import base64
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from quiz_core import validate_quiz, fingerprint, read_json


def render(q):
    validate_quiz(q)
    script = Path(__file__).absolute()
    if script.is_symlink() or script.parent.is_symlink() or script.parent.parent.is_symlink():
        raise ValueError('请通过 Skill 实际源目录调用脚本，不使用符号链接路径')
    root = script.parent.parent.resolve()
    template = root / 'assets' / 'quiz.html'
    if template.is_symlink() or template.parent.is_symlink() or template.resolve().parent != root / 'assets':
        raise ValueError('模板路径不在固定资源目录')
    content = template.read_text(encoding='utf-8')
    if content.count('__QUIZ_BASE64__') != 1:
        raise ValueError('模板标记无效')
    payload = base64.b64encode(json.dumps({'quiz': q, 'fingerprint': fingerprint(q)}, ensure_ascii=False).encode()).decode()
    return content.replace('__QUIZ_BASE64__', payload)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 1:
            raise ValueError('不接受路径或参数；仅从 stdin 读取 JSON')
        result = render(read_json(sys.stdin.buffer))
        sys.stdout.write(result)
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print('无法生成试卷：' + str(exc), file=sys.stderr)
        sys.exit(2)
