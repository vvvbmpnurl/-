import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import server as app

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(app, 'DB', Path(self.tmp.name) / 'test.db')
        self.db.start()
        self.env = patch.dict(os.environ, {
            'AVATAR_GATEWAY_URL':'https://avatar.example', 'AVATAR_GATEWAY_TOKEN':'secret',
            'DASHSCOPE_API_KEY':'secret', 'HEYGEN_API_KEY':'secret', 'HEYGEN_AVATAR_ID':'avatar', 'HEYGEN_VOICE_ID':'voice',
            'PUBLISH_GATEWAY_URL':'https://publish.example', 'PUBLISH_GATEWAY_TOKEN':'secret',
            'PUBLISH_ACCOUNTS':json.dumps([dict(id='a',name='门店A',platform='dy'), dict(id='b',name='门店B',platform='sph')])}, clear=True)
        self.env.start()
        app.init_db()

    def tearDown(self):
        self.env.stop()
        self.db.stop()
        self.tmp.cleanup()

    def ready(self, approved=True):
        with patch.object(app, 'remote', return_value={'task_id':'t1'}):
            j = app.create_job(dict(title='选题',script='完整口播',provider='domestic'))
        with patch.object(app, 'remote', return_value={'status':'completed','video_url':'https://cdn.example/one.mp4'}):
            j = app.refresh_job(j['id'])
        if approved:
            j = app.review_job(j['id'], dict(decision='approved',watched=True))
        return j

    def test_domestic_snapshot_and_completion(self):
        data = dict(title='选题',script='选题原稿',provider='domestic')
        with patch.object(app,'remote',return_value={'task_id':'task'}) as upstream:
            j = app.create_job(data)
            self.assertEqual(upstream.call_args.args[3]['script'], '选题原稿')
        data['script']='已修改'
        self.assertEqual(app.get_job(j['id'])['script'],'选题原稿')
        with patch.object(app,'remote',return_value={'status':'completed','video_url':'https://cdn.example/v.mp4'}):
            self.assertEqual(app.refresh_job(j['id'])['status'],'ready')

    def test_provider_mappings(self):
        with patch.object(app,'remote',return_value={'output':{'task_id':'wan1'}}) as request:
            j=app.create_job(dict(title='空镜',script='教室窗边',provider='wan'))
            self.assertEqual(request.call_args.args[3]['parameters']['duration'],5)
        with patch.object(app,'remote',return_value={'output':{'task_status':'SUCCEEDED','video_url':'https://cdn.example/v.mp4'}}):
            self.assertEqual(app.refresh_job(j['id'])['status'],'ready')
        with patch.object(app,'remote',return_value={'data':{'video_id':'hey1'}}) as request:
            j=app.create_job(dict(title='口播',script='完整稿',provider='heygen'))
            self.assertEqual(request.call_args.args[3]['video_inputs'][0]['voice']['input_text'],'完整稿')
        with patch.object(app,'remote',return_value={'data':{'status':'failed'}}):
            self.assertEqual(app.refresh_job(j['id'])['status'],'failed')

    def test_no_provider_no_charge(self):
        with patch.dict(os.environ,{'AVATAR_GATEWAY_TOKEN':''}), patch.object(app,'remote') as request:
            with self.assertRaises(app.Problem): app.create_job(dict(title='a',script='b',provider='domestic'))
            request.assert_not_called()

    def test_review_gate(self):
        j=self.ready(False)
        with patch.object(app,'remote') as request:
            with self.assertRaises(app.Problem): app.publish(j['id'],{'accounts':['a']})
            request.assert_not_called()
        with self.assertRaises(app.Problem): app.review_job(j['id'],dict(decision='approved',watched=False))
        with self.assertRaises(app.Problem): app.review_job(j['id'],dict(decision='rejected'))
        app.review_job(j['id'],dict(decision='rejected',note='字幕需修改'))
        with self.assertRaises(app.Problem): app.publish(j['id'],{'accounts':['a']})

    def test_batch_partial_results_and_no_duplicates(self):
        j=self.ready()
        responses=[{'publication_id':'p1','status':'published','url':'https://dy.example/v'},app.Problem('timeout')]
        with patch.object(app,'remote',side_effect=responses) as request:
            result=app.publish(j['id'],{'accounts':['a','a','b']})
            self.assertEqual([x['status'] for x in result],['published','unknown'])
            self.assertEqual(request.call_count,2)
        with patch.object(app,'remote') as request:
            app.publish(j['id'],{'accounts':['a','b']})
            request.assert_not_called()
        self.assertEqual(len(app.rows('deliveries')),2)
        with self.assertRaises(app.Problem): app.review_job(j['id'],dict(decision='rejected',note='撤回'))

    def test_submitted_is_not_published(self):
        j=self.ready()
        with patch.object(app,'remote',return_value={'publication_id':'p1','status':'submitted'}):
            d=app.publish(j['id'],{'accounts':['a']})[0]
        self.assertEqual(d['status'],'submitted')
        with patch.object(app,'remote',return_value={'publication_id':'p1','status':'published'}):
            self.assertEqual(app.refresh_delivery(d['id'])['status'],'published')

    def test_invalid_receipt_and_bad_account(self):
        j=self.ready()
        with self.assertRaises(app.Problem): app.publish(j['id'],{'accounts':['unauthorized']})
        with patch.object(app,'remote',return_value={'status':'published'}):
            self.assertEqual(app.publish(j['id'],{'accounts':['a']})[0]['status'],'unknown')

    def test_submission_timeout_survives_restart(self):
        with patch.object(app,'remote',side_effect=app.Problem('timeout')):
            j=app.create_job(dict(title='选题',script='稿',provider='domestic'))
        self.assertEqual(j['status'],'unknown')
        j['status']='creating'; app.persist('jobs',j)
        app.init_db()
        self.assertEqual(app.get_job(j['id'])['status'],'unknown')
        j=self.ready()
        d=dict(id='d1',job=j['id'],account='a',status='sending')
        app.persist('deliveries',d); app.init_db()
        self.assertEqual(app.rows('deliveries')[0]['status'],'unknown')

    def test_http_security_and_static_allowlist(self):
        service=app.ThreadingHTTPServer(('127.0.0.1',0), app.Handler)
        thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{service.server_port}'
        try:
            state=json.load(urlopen(base+'/api/factory/state'))
            self.assertNotIn('secret',json.dumps(state))
            with urlopen(base+'/') as response:
                self.assertTrue(response.read().startswith(b'<!DOCTYPE html>'))
            for path in ('/server.py','/.env','/data/factory.db'):
                with self.assertRaises(HTTPError) as err: urlopen(base+path)
                self.assertEqual(err.exception.code,404)
            with self.assertRaises(HTTPError) as err:
                urlopen(Request(base+'/api/factory/jobs',data=b'{}',method='POST'))
            self.assertEqual(err.exception.code,403)
            with self.assertRaises(HTTPError) as err:
                urlopen(Request(base+'/api/factory/state',headers={'Host':'evil.example'}))
            self.assertEqual(err.exception.code,403)
            req=Request(base+'/api/factory/jobs', data=json.dumps(dict(title='视频',script='稿',provider='domestic')).encode(),
                        headers={'Origin':base,'X-Factory-CSRF':state['csrf'],'Content-Type':'application/json'})
            with patch.object(app,'remote',return_value={'task_id':'real-shape'}):
                self.assertEqual(json.load(urlopen(req))['status'],'processing')
        finally:
            service.shutdown();service.server_close();thread.join()

if __name__ == '__main__': unittest.main()
