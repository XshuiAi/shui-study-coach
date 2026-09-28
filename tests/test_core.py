import ast
import copy
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from quiz_core import validate_quiz, validate_attempt, fingerprint, score, score_followup, read_json
from render_quiz import render


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.q = json.loads((ROOT/'examples/english-reading.json').read_text())
        self.a = dict(schema=1, quizId=self.q['id'], fingerprint=fingerprint(self.q), mode='practice', answers={}, hints={}, flags={}, submitted=True, startedAt=1000, updatedAt=3000, submittedAt=2000)

    def test_original_samples_and_sources(self):
        for p in (ROOT/'examples').glob('*.json'):
            q = validate_quiz(json.loads(p.read_text()))
            self.assertIn('<!doctype html>', render(q))

    def test_multiselect_all_subsets(self):
        item = self.q['questions'][2]
        for n in range(5):
            for chosen in itertools.combinations(range(4), n):
                self.a['answers'][item['id']] = list(chosen)
                self.assertEqual(score(self.q,self.a)[2]['correct'],set(chosen)==set(item['answer']))

    def test_hints_unanswered_and_flags(self):
        self.a['answers']={'q1':[1],'q2':[0],'q3':[0,2]}
        self.a['hints']={'q1':True}
        self.a['flags']={'q3':True}
        self.assertEqual([r['status'] for r in score(self.q,self.a)],['提示后正确','需复习','独立正确','未作答'])
        self.assertTrue(score(self.q,self.a)[2]['flagged'])

    def test_reject_unknown_and_forged_fields(self):
        for key,val in [('score',999),('output','/'),('__proto__',{})]:
            a=copy.deepcopy(self.a);a[key]=val
            with self.assertRaises(ValueError):validate_attempt(self.q,a)
        a=copy.deepcopy(self.a);a['answers']={'unknown':[0]}
        with self.assertRaises(ValueError):validate_attempt(self.q,a)
        a=copy.deepcopy(self.a);a['mode']='exam';a['hints']={'q1':True}
        with self.assertRaises(ValueError):validate_attempt(self.q,a)

    def test_version_and_options(self):
        a=copy.deepcopy(self.a);a['fingerprint']='0'*64
        with self.assertRaises(ValueError):validate_attempt(self.q,a)
        for value in [[9],[True],[0,0],[0,1]]:
            a=copy.deepcopy(self.a);a['answers']={'q1':value}
            with self.assertRaises(ValueError):validate_attempt(self.q,a)

    def test_invalid_question_evidence(self):
        q=copy.deepcopy(self.q);q['questions'][0]['evidence']='not in source'
        with self.assertRaises(ValueError):validate_quiz(q)
        q=copy.deepcopy(self.q);q['questions'][0]['options'][1]=q['questions'][0]['options'][0]
        with self.assertRaises(ValueError):validate_quiz(q)

    def test_injection_encoded_as_data(self):
        q=copy.deepcopy(self.q);attack='</script><script>alert(1)</script>'
        q['title']=attack;q['questions'][0]['options'][0]='<img src=x onerror=alert(1)>'
        html=render(q)
        self.assertNotIn(attack,html)
        self.assertNotIn('<img src=x',html)
        self.assertNotIn('innerHTML',html)
        self.assertIn("connect-src 'none'",html)

    def test_json_limits_and_duplicates(self):
        for raw in [b'{"a":1,"a":2}', b'x'*1000001,b'no-json']:
            with self.assertRaises(ValueError):read_json(io.BytesIO(raw))

    def test_cli_paths_rejected_without_mutation(self):
        tmp=Path(tempfile.mkdtemp(prefix='study-p0-'))
        sentinel=tmp/'existing.txt';sentinel.write_text('keep this')
        link=tmp/'link';link.symlink_to(ROOT)
        before={p.name: (p.is_symlink(),p.read_bytes() if p.is_file() and not p.is_symlink() else None) for p in tmp.iterdir()}
        paths=['.','..','/','~',str(Path.cwd()),str(ROOT),str(ROOT.parent),str(ROOT/'assets'),str(ROOT/'examples'),str(tmp),str(link),'../outside','/tmp/out.html','--force','--overwrite','--delete','--clean','--output']
        for script in ['render_quiz.py','review_attempt.py']:
            for arg in paths:
                p=subprocess.run([sys.executable,str(ROOT/'scripts'/script),arg],input=b'{}',capture_output=True,cwd=tmp)
                self.assertEqual(p.returncode,2,(script,arg,p.stderr))
                self.assertEqual(p.stdout,b'')
        after={p.name: (p.is_symlink(),p.read_bytes() if p.is_file() and not p.is_symlink() else None) for p in tmp.iterdir()}
        self.assertEqual(before,after)

    def test_template_symlink_rejected(self):
        tmp=Path(tempfile.mkdtemp(prefix='study-template-'))
        (tmp/'scripts').mkdir();(tmp/'assets').mkdir()
        for f in ['render_quiz.py','quiz_core.py']:
            (tmp/'scripts'/f).write_bytes((ROOT/'scripts'/f).read_bytes())
        (tmp/'assets'/'quiz.html').symlink_to(ROOT/'assets/quiz.html')
        p=subprocess.run([sys.executable,str(tmp/'scripts/render_quiz.py')],input=json.dumps(self.q).encode(),capture_output=True)
        self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,b'')

    def test_readonly_script_static_guard(self):
        banned={'exec','eval','system','popen','unlink','rmdir','rmtree','write_text','write_bytes','remove','rename','replace','copy','copytree','urlopen'}
        for f in (ROOT/'scripts').glob('*.py'):
            tree=ast.parse(f.read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.Call):
                    name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
                    # str.replace only substitutes the fixed HTML marker.
                    if name=='replace' and f.name=='render_quiz.py':continue
                    self.assertNotIn(name,banned,f.name)

    def test_review_recomputes(self):
        self.a['answers']={q['id']:q['answer'] for q in self.q['questions']}
        p=subprocess.run([sys.executable,str(ROOT/'scripts/review_attempt.py')],input=json.dumps({'quiz':self.q,'attempt':self.a}).encode(),capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['correct'],4)
        self.a['submitted']=False;self.a['submittedAt']=None
        p=subprocess.run([sys.executable,str(ROOT/'scripts/review_attempt.py')],input=json.dumps({'quiz':self.q,'attempt':self.a}).encode(),capture_output=True)
        self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,b'')

    def test_cet6_targeted_followup_and_tamper_rejection(self):
        q=json.loads((ROOT/'examples/cet6-careful-reading.json').read_text())
        validate_quiz(q)
        self.assertEqual(len(q['questions']),5)
        self.assertTrue(400<=len(q['sources'][0]['text'].split())<=450)
        a=dict(schema=1,quizId=q['id'],fingerprint=fingerprint(q),mode='practice',
               answers={'q1':[0],'q2':[0],'q3':[0],'q4':[2],'q5':[1]},
               hints={'q4':True},flags={},submitted=True,
               startedAt=1000,updatedAt=5000,submittedAt=2000,
               followup=dict(questionIds=['f2','f3','f4'],
                             answers={'f2':[1],'f3':[0],'f4':[0]},
                             submitted=True,startedAt=3000,updatedAt=4500,submittedAt=4000))
        validate_attempt(q,a)
        self.assertEqual(sum(r['correct'] for r in score(q,a)),3)
        self.assertEqual(sum(r['correct'] for r in score_followup(q,a)),2)
        for change in [
            lambda f:f['questionIds'].append('f1'),
            lambda f:f['answers'].update({'f1':[0]}),
            lambda f:f.update({'startedAt':1}),
            lambda f:f.update({'submittedAt':6000}),
        ]:
            bad=copy.deepcopy(a);change(bad['followup'])
            with self.assertRaises(ValueError):validate_attempt(q,bad)
        p=subprocess.run([sys.executable,str(ROOT/'scripts/review_attempt.py')],
                         input=json.dumps({'quiz':q,'attempt':a}).encode(),capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        self.assertEqual(result['followup']['correct'],2)
        self.assertEqual(result['nextReview'],['q2','q3','q4'])

    def test_reject_invalid_followup_content(self):
        q=json.loads((ROOT/'examples/cet6-careful-reading.json').read_text())
        bad=copy.deepcopy(q);bad['followups'][0]['target_id']='unknown'
        with self.assertRaises(ValueError):validate_quiz(bad)
        bad=copy.deepcopy(q);bad['questions'][0]['option_feedback']=['one']
        with self.assertRaises(ValueError):validate_quiz(bad)
        bad=copy.deepcopy(q);bad['followups'][0]['evidence']='not in passage'
        with self.assertRaises(ValueError):validate_quiz(bad)


if __name__=='__main__':unittest.main(verbosity=2)
