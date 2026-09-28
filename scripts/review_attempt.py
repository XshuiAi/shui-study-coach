#!/usr/bin/env python3
"""stdin {quiz, attempt} -> stdout reviewed JSON. No file writes."""
import json
import sys
sys.dont_write_bytecode = True
from quiz_core import read_json, validate_quiz, fields, score, score_followup

if __name__ == '__main__':
    try:
        if len(sys.argv) != 1:
            raise ValueError('不接受路径或参数；仅从 stdin 读取 JSON')
        data = read_json(sys.stdin.buffer)
        fields(data, ['quiz', 'attempt'])
        q = validate_quiz(data['quiz'])
        a = data['attempt']
        rows = score(q, a)
        if not a['submitted']:
            raise ValueError('尚未交卷：可继续学习，不生成最终成绩')
        followup = score_followup(q, a)
        result = {'quizId': q['id'], 'total': len(rows), 'correct': sum(r['correct'] for r in rows), 'independentCorrect': sum(r['correct'] and not r['hint'] for r in rows), 'unanswered': sum(not r['chosen'] for r in rows), 'rows': rows, 'nextReview': [r['id'] for r in rows if not r['correct'] or r['hint'] or r['flagged']], 'followup': {'total': len(followup), 'correct': sum(r['correct'] for r in followup), 'rows': followup} if followup else None, 'notice': '依据原卷重算；选项反馈是待核对的错因线索。自报记录不证明闭卷、身份或真实时长，新题答对一次也不等于稳定掌握。'}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, UnicodeError, TypeError) as exc:
        print('无法核对记录：' + str(exc), file=sys.stderr)
        sys.exit(2)
