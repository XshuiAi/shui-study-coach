"""Pure validation and scoring. No writes, network or dynamic execution."""
import hashlib
import json
import re

MAX_BYTES = 1_000_000


def text(value, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('文字不能为空或超过长度限制')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value):
        raise ValueError('ID 只允许字母开头的小写字母、数字和横线')


def fields(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= set(obj) or set(obj) - set(required) - set(optional):
        raise ValueError('字段缺失或包含未知字段')


def validate_quiz(q):
    fields(q, ['schema', 'id', 'title', 'subject', 'scope', 'minutes', 'sources', 'questions'], ['profile', 'followups'])
    if type(q['schema']) is not int or q['schema'] != 1:
        raise ValueError('试卷版本不支持')
    identifier(q['id'])
    for k in ['title', 'subject', 'scope']:
        text(q[k], 1000)
    if 'profile' in q:
        fields(q['profile'], ['exam', 'module', 'material', 'goal'])
        for value in q['profile'].values():
            text(value, 500)
    if type(q['minutes']) is not int or not 1 <= q['minutes'] <= 120:
        raise ValueError('时间须为 1—120 分钟')
    if not isinstance(q['sources'], list) or not 1 <= len(q['sources']) <= 20:
        raise ValueError('材料数量须为 1—20')
    sources = {}
    for s in q['sources']:
        fields(s, ['id', 'title', 'text'])
        identifier(s['id'])
        if s['id'] in sources:
            raise ValueError('材料 ID 重复')
        text(s['title'], 300)
        text(s['text'], 50000)
        sources[s['id']] = s
    if not isinstance(q['questions'], list) or not 1 <= len(q['questions']) <= 30:
        raise ValueError('题量须为 1—30')
    ids = set()
    def check_item(item, is_followup=False):
        required = ['id', 'type', 'skill', 'prompt', 'options', 'answer', 'source_id', 'location', 'evidence', 'explanation', 'hint']
        fields(item, required + (['target_id'] if is_followup else []), ['option_feedback', 'next_action'])
        identifier(item['id'])
        if item['id'] in ids:
            raise ValueError('题目 ID 重复')
        ids.add(item['id'])
        if item['type'] not in ['single', 'multiple', 'truefalse']:
            raise ValueError('只支持 single / multiple / truefalse')
        for k in ['skill', 'prompt', 'location', 'evidence', 'explanation', 'hint']:
            text(item[k])
        opts = item['options']
        if not isinstance(opts, list) or not 2 <= len(opts) <= 6:
            raise ValueError('选项须为 2—6 项')
        for o in opts:
            text(o, 2000)
        if len({o.strip() for o in opts}) != len(opts):
            raise ValueError('选项重复')
        if 'option_feedback' in item:
            if not isinstance(item['option_feedback'], list) or len(item['option_feedback']) != len(opts):
                raise ValueError('选项反馈须与选项逐项对应')
            for note in item['option_feedback']:
                text(note, 1000)
        if 'next_action' in item:
            text(item['next_action'], 1000)
        ans = item['answer']
        if not isinstance(ans, list) or not ans or any(type(a) is not int or not 0 <= a < len(opts) for a in ans) or len(set(ans)) != len(ans):
            raise ValueError('答案索引错误')
        if item['type'] != 'multiple' and len(ans) != 1:
            raise ValueError('单选或判断只能有一个答案')
        if item['type'] == 'truefalse' and len(opts) != 2:
            raise ValueError('判断题只能两个选项')
        if not isinstance(item['source_id'], str) or item['source_id'] not in sources:
            raise ValueError('材料来源不存在')
        if item['evidence'] not in sources[item['source_id']]['text']:
            raise ValueError('答案依据不在原文中')
    for item in q['questions']:
        check_item(item)
    if 'followups' in q:
        if not isinstance(q['followups'], list) or len(q['followups']) > 30:
            raise ValueError('复测题数量须为 0—30')
        targets = set()
        base_ids = {item['id'] for item in q['questions']}
        for item in q['followups']:
            if not isinstance(item, dict) or item.get('target_id') not in base_ids:
                raise ValueError('复测题须指向本卷题目')
            if item['target_id'] in targets:
                raise ValueError('每道原题最多对应一道复测题')
            targets.add(item['target_id'])
            check_item(item, True)
    return q


def fingerprint(q):
    return hashlib.sha256(json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_attempt(q, a):
    fields(a, ['schema', 'quizId', 'fingerprint', 'mode', 'answers', 'hints', 'flags', 'submitted', 'startedAt', 'updatedAt', 'submittedAt'], ['followup'])
    if type(a['schema']) is not int or a['schema'] != 1 or a['quizId'] != q['id'] or a['fingerprint'] != fingerprint(q):
        raise ValueError('作答记录与试卷版本不匹配')
    if a['mode'] not in ['practice', 'exam'] or type(a['submitted']) is not bool:
        raise ValueError('作答模式或状态错误')
    for k in ['startedAt', 'updatedAt']:
        if type(a[k]) is not int or not 0 < a[k] <= 8_640_000_000_000_000:
            raise ValueError('日期字段错误')
    if a['submitted']:
        if type(a['submittedAt']) is not int or not a['startedAt'] <= a['submittedAt'] <= a['updatedAt']:
            raise ValueError('交卷日期错误')
    elif a['submittedAt'] is not None:
        raise ValueError('未交卷不能有交卷日期')
    if a['updatedAt'] < a['startedAt']:
        raise ValueError('日期顺序错误')
    ids = {i['id']: i for i in q['questions']}
    for name in ['answers', 'hints', 'flags']:
        if not isinstance(a[name], dict) or set(a[name]) - set(ids):
            raise ValueError('记录含未知题目')
    for key, vals in a['answers'].items():
        if not isinstance(vals, list) or any(type(v) is not int or not 0 <= v < len(ids[key]['options']) for v in vals) or len(vals) != len(set(vals)):
            raise ValueError('作答选项错误')
        if ids[key]['type'] != 'multiple' and len(vals) > 1:
            raise ValueError('单选记录含多个选项')
    for name in ['hints', 'flags']:
        if any(type(v) is not bool for v in a[name].values()):
            raise ValueError('提示或标记错误')
    if a['mode'] == 'exam' and any(a['hints'].values()):
        raise ValueError('自测记录不能含提示')
    if 'followup' in a and a['followup'] is not None:
        if not a['submitted'] or not q.get('followups'):
            raise ValueError('未交卷或无复测题，不能有复测记录')
        f = a['followup']
        fields(f, ['questionIds', 'answers', 'submitted', 'startedAt', 'updatedAt', 'submittedAt'])
        if type(f['submitted']) is not bool or not isinstance(f['questionIds'], list):
            raise ValueError('复测记录格式错误')
        needs = {r['id'] for r in score(q, {k: v for k, v in a.items() if k != 'followup'}) if not r['correct'] or r['hint'] or r['flagged']}
        selected = [item for item in q['followups'] if item['target_id'] in needs]
        if f['questionIds'] != [item['id'] for item in selected] or not selected:
            raise ValueError('复测题与首轮结果不匹配')
        if not isinstance(f['answers'], dict) or set(f['answers']) - set(f['questionIds']):
            raise ValueError('复测答案包含未知题目')
        by_id = {item['id']: item for item in selected}
        for key, vals in f['answers'].items():
            item = by_id[key]
            if not isinstance(vals, list) or len(vals) != len(set(vals)) or any(type(v) is not int or not 0 <= v < len(item['options']) for v in vals) or (item['type'] != 'multiple' and len(vals) > 1):
                raise ValueError('复测答案索引错误')
        for key in ['startedAt', 'updatedAt']:
            if type(f[key]) is not int or not a['submittedAt'] <= f[key] <= 8_640_000_000_000_000:
                raise ValueError('复测日期错误')
        if f['updatedAt'] < f['startedAt']:
            raise ValueError('复测日期顺序错误')
        if f['submitted']:
            if type(f['submittedAt']) is not int or not f['startedAt'] <= f['submittedAt'] <= f['updatedAt']:
                raise ValueError('复测交卷日期错误')
        elif f['submittedAt'] is not None:
            raise ValueError('未交复测卷不能有交卷日期')
    return a


def score(q, a):
    validate_attempt(q, a)
    rows = []
    for item in q['questions']:
        chosen = a['answers'].get(item['id'], [])
        correct = set(chosen) == set(item['answer'])
        hint = a['hints'].get(item['id'], False)
        status = '未作答' if not chosen else ('提示后正确' if hint else '独立正确') if correct else '需复习'
        issue = ''
        if chosen and not correct and item.get('option_feedback') and item['type'] != 'multiple':
            issue = item['option_feedback'][chosen[0]]
        rows.append({'id': item['id'], 'skill': item['skill'], 'chosen': chosen, 'correct': correct, 'hint': hint, 'status': status, 'flagged': a['flags'].get(item['id'], False), 'issue': issue})
    return rows


def score_followup(q, a):
    validate_attempt(q, a)
    f = a.get('followup')
    if not f or not f['submitted']:
        return []
    selected = {item['id']: item for item in q.get('followups', []) if item['id'] in f['questionIds']}
    return [{'id': item_id, 'targetId': selected[item_id]['target_id'],
             'skill': selected[item_id]['skill'],
             'chosen': f['answers'].get(item_id, []),
             'correct': set(f['answers'].get(item_id, [])) == set(selected[item_id]['answer'])}
            for item_id in f['questionIds']]


def read_json(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('数据超过 1 MB')
    def unique(pairs):
        d = {}
        for key, val in pairs:
            if key in d:
                raise ValueError('JSON 存在重复字段')
            d[key] = val
        return d
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
