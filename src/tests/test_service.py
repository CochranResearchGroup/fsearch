"""Public service/client tests; owned synthetic snapshots only."""
import base64, json, os, subprocess, sys, tempfile, unittest, signal, time, socket, struct
from contextlib import contextmanager
import shutil, ctypes, uuid
ctypes.CDLL(None).prctl(36,1,0,0,0)  # Test-harness subreaper: own detached fixture services and orphaned workers.
from pathlib import Path
SERVICE, CLI, FIXTURE, FAULT = sys.argv[1:5]
class WarmService(unittest.TestCase):
    def test_previous_boot_startup_serves_cached_snapshot(self):
        with self.owned_service(previous_boot=True) as (_,root,_,sock,_):
            shutil.rmtree(root)
            with self.request(sock) as connection: result=self.receive(connection)
            self.assertEqual(result['status'],'ok')
            self.assertEqual(len(result['results']),1)

    def test_short_ascii_literal_rejects_nonmatching_unicode_before_verification_budget(self):
        names=[f'обычный-{i:04d}.txt' for i in range(128)]+['документ??.pdf','полноширинный？？.pdf']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'unicode-short-budget','query':'??','kind':'files','max_candidates':1}
            with self.request(sock,query) as connection:result=self.receive(connection)
            self.assertTrue(result['complete'],result)
            self.assertEqual([row['path'] for row in result['results']],[str(root/'документ??.pdf')])
    def test_refresh_during_serving_requires_explicit_replacement(self):
        with self.owned_service() as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'refresh-serving','query':'pdf','kind':'files'}
            with self.request(sock,query) as connection:before=self.receive(connection)
            old_worker=json.loads(Path(str(sock)+'.state').read_text())['worker']
            (root/'next-only.pdf').touch()
            refresh=Path(SERVICE).with_name('fsearch-refresh')
            scanner_fault=Path(FAULT).with_name('librefresh_fault_fixture.so')
            env=dict(os.environ,LD_PRELOAD=str(scanner_fault),FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='350')
            process=subprocess.Popen(['python3',str(refresh),'refresh','--root',str(root),'--database',str(snapshot)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                refresh_state=Path(str(snapshot)+'.refresh.state');deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    if refresh_state.exists() and json.loads(refresh_state.read_text())['phase']=='starting':break
                    time.sleep(.005)
                else:self.fail('refresh did not record its active scanner')
                with self.request(sock,query) as connection:during=self.receive(connection)
                self.assertEqual(during['results'],before['results']);self.assertEqual(during['snapshot']['identity'],before['snapshot']['identity'])
                output,error=process.communicate(timeout=5)
                self.assertEqual(process.returncode,0,output+error);self.assertEqual(json.loads(output)['status'],'published')
                with self.request(sock,query) as connection:published=self.receive(connection)
                self.assertEqual(published['results'],before['results']);self.assertEqual(published['snapshot']['identity'],before['snapshot']['identity'])
                self.assertEqual(json.loads(Path(str(sock)+'.state').read_text())['worker'],old_worker)
                replaced=subprocess.run([SERVICE,'replace','--socket',str(sock),'--candidate-database',str(snapshot)],capture_output=True,text=True,timeout=5)
                self.assertEqual(replaced.returncode,0,replaced.stdout+replaced.stderr)
                with self.request(sock,query) as connection:after=self.receive(connection)
                self.assertEqual([row['path'] for row in after['results']],[str(root/'invoice.pdf'),str(root/'next-only.pdf')])
                self.assertNotEqual(after['snapshot']['identity'],before['snapshot']['identity'])
                self.assertEqual(after['snapshot']['identity'],json.loads(replaced.stdout)['snapshot_id'])
            finally:
                if process.poll() is None:process.kill()
                process.communicate(timeout=5)
    def test_replacement_and_queries_do_not_access_removed_roots(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-replace-trace-') as temporary:
            work=Path(temporary);snapshot=work/'snapshot.db';candidate=work/'candidate.db';sock=work/'search.sock';trace=work/'replacement.trace'
            roots=[work/'old-root',work/'new-root']
            for database,root,name in zip((snapshot,candidate),roots,('old-only.pdf','new-only.pdf')):
                root.mkdir();(root/name).touch()
                built=subprocess.run([FIXTURE,'build',str(database),str(root)],capture_output=True,text=True,timeout=10)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr);database.chmod(0o600);shutil.rmtree(root)
            server=subprocess.Popen(['strace','--kill-on-exit','-f','-yy','-s','4096','-e','trace=%file,getdents64','-o',str(trace),SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                query={'schema_version':1,'request_id':'trace-query','query':'pdf','kind':'files'}
                with self.request(sock,query) as connection:before=self.receive(connection)
                self.assertEqual([row['path'] for row in before['results']],[str(roots[0]/'old-only.pdf')])
                replaced=subprocess.run([SERVICE,'replace','--socket',str(sock),'--candidate-database',str(candidate)],capture_output=True,text=True,timeout=5)
                self.assertEqual(replaced.returncode,0,replaced.stdout+replaced.stderr)
                self.assertEqual(json.loads(replaced.stdout)['status'],'replaced')
                with self.request(sock,query) as connection:after=self.receive(connection)
                self.assertEqual([row['path'] for row in after['results']],[str(roots[1]/'new-only.pdf')])
                stopped=subprocess.run([SERVICE,'stop','--socket',str(sock)],capture_output=True,text=True,timeout=5)
                self.assertEqual(stopped.returncode,0,stopped.stdout+stopped.stderr)
                output,error=server.communicate(timeout=5)
                self.assertEqual(server.returncode,0,output+error)
                calls=trace.read_text()
                evidence=os.environ.get('FSEARCH_TEST_EVIDENCE_DIR')
                if evidence:
                    destination=Path(evidence);destination.mkdir(parents=True,exist_ok=True)
                    (destination/'replacement-root-isolation.trace').write_text(calls)
                for root in roots:self.assertNotIn(str(root),calls,'Replacement or query accessed an indexed root')
                self.assertIn(str(snapshot),calls);self.assertIn(str(candidate),calls)
                # Python import discovery can enumerate runtime directories;
                # the forbidden boundary is either indexed root, across all processes.
            finally:
                if server.poll() is None:server.kill()
                server.communicate(timeout=5)
    def tearDown(self):
        for _ in range(100):
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if pid==0: time.sleep(.005); continue
            except ChildProcessError: break

    def stop_owned_service(self, sock):
        state=json.loads(Path(str(sock)+'.state').read_text())
        pid=state['supervisor']['pid']
        result=subprocess.run([SERVICE,'stop','--socket',str(sock)],capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                reaped,_=os.waitpid(pid,os.WNOHANG)
                if reaped==pid: return
            except ChildProcessError:
                self.fail('Owned supervisor was not available for a proved reap')
            time.sleep(.005)
        self.fail('Owned supervisor did not exit after stop acknowledgement')

    def test_client_starts_service_and_reuses_removed_root_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-test-') as temporary:
            work=Path(temporary); root=work/'owned'; root.mkdir(); (root/'invoice.pdf').touch()
            snapshot=work/'snapshot.db'
            subprocess.run([FIXTURE,'build',str(snapshot),str(root)],check=True,capture_output=True,timeout=10)
            snapshot.chmod(0o600); (root/'invoice.pdf').unlink(); root.rmdir()
            sock=work/'search.sock'
            try:
                for _ in range(2):
                    result=subprocess.run([CLI,'--socket',str(sock),'--database',str(snapshot),'--query','invoice'],capture_output=True,text=True,timeout=5)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    payload=json.loads(result.stdout); self.assertTrue(payload['complete'])
                    self.assertEqual([row['path'] for row in payload['results']],[str(root/'invoice.pdf')])
                state=json.loads((work/'search.sock.state').read_text())
                self.assertEqual(state['phase'],'ready')
            finally:
                self.stop_owned_service(sock)
    def test_invalid_replacement_preserves_accepted_results_and_worker(self):
        with self.owned_service() as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'before','query':'invoice'}
            with self.request(sock,query) as connection:before=self.receive(connection)
            worker=json.loads(Path(str(sock)+'.state').read_text())['worker']
            replacement={'schema_version':1,'request_id':'replace-invalid','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(work/'missing.db')).decode()}
            with self.request(sock,replacement) as connection:failed=self.receive(connection)
            self.assertEqual(failed.get('error',{}).get('code'),'snapshot_unavailable',failed)
            with self.request(sock,query) as connection:after=self.receive(connection)
            self.assertEqual(after['results'],before['results']);self.assertEqual(after['snapshot']['identity'],before['snapshot']['identity'])
            self.assertEqual(json.loads(Path(str(sock)+'.state').read_text())['worker'],worker)

    def test_inflight_query_keeps_old_identity_until_completion(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-query-switch-') as faults:
            marker=Path(faults)/'query-started'
            with self.owned_service({'FSEARCH_FIXTURE_QUERY_DELAY_MS':'500','FSEARCH_FIXTURE_MARKER':str(marker)}) as (work,root,snapshot,sock,server):
                state_path=Path(str(sock)+'.state')
                candidate=work/'next.db';newroot=work/'next-root';newroot.mkdir();(newroot/'new-only.pdf').touch()
                built=subprocess.run([FIXTURE,'build',str(candidate),str(newroot)],capture_output=True,text=True,timeout=5)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr);candidate.chmod(0o600)
                query={'schema_version':1,'request_id':'inflight-old','query':'pdf','kind':'files','timeout_ms':1500}
                with self.request(sock,query) as querying:
                    deadline=time.monotonic()+1
                    while not marker.exists() and time.monotonic()<deadline:time.sleep(.005)
                    self.assertTrue(marker.exists(),'query delay adapter did not execute')
                    state=json.loads(state_path.read_text());self.assertEqual(state['phase'],'ready')
                    identity=state['snapshot_id'];old_worker=state['worker']
                    replacement={'schema_version':1,'request_id':'inflight-replace','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(candidate)).decode()}
                    with self.request(sock,replacement) as replacing:
                        deadline=time.monotonic()+.2
                        while time.monotonic()<deadline:
                            state=json.loads(state_path.read_text())
                            if state.get('candidate_worker'):break
                            time.sleep(.005)
                        self.assertIsNotNone(state.get('candidate_worker'));self.assertEqual(state['worker'],old_worker)
                        old=self.receive(querying)
                        self.assertEqual(old['snapshot']['identity'],identity)
                        self.assertEqual([row['path'] for row in old['results']],[str(root/'invoice.pdf')])
                        accepted=self.receive(replacing)
                        self.assertEqual(accepted['status'],'replaced',accepted)
                with self.request(sock,query) as connection:new=self.receive(connection)
                self.assertEqual(new['snapshot']['identity'],accepted['snapshot_id']);self.assertNotEqual(new['snapshot']['identity'],identity)
                self.assertEqual([row['path'] for row in new['results']],[str(newroot/'new-only.pdf')])

    def test_oversize_candidate_preserves_accepted_worker_and_results(self):
        with self.owned_service() as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'budget-old','query':'invoice'}
            with self.request(sock,query) as connection:before=self.receive(connection)
            worker=json.loads(Path(str(sock)+'.state').read_text())['worker']
            candidate=work/'oversize.db'
            with candidate.open('wb') as stream:stream.truncate(64*1024*1024+1)
            candidate.chmod(0o600)
            replacement={'schema_version':1,'request_id':'oversize-candidate','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(candidate)).decode()}
            with self.request(sock,replacement) as connection:failed=self.receive(connection)
            self.assertEqual(failed.get('error',{}).get('code'),'snapshot_size_limit',failed)
            state=json.loads(Path(str(sock)+'.state').read_text())
            self.assertEqual(state['worker'],worker);self.assertIsNone(state['candidate_worker']);self.assertEqual(state['phase'],'ready')
            with self.request(sock,query) as connection:after=self.receive(connection)
            self.assertEqual(after['results'],before['results']);self.assertEqual(after['snapshot']['identity'],before['snapshot']['identity'])

    def test_candidate_deadline_preserves_accepted_worker_and_results(self):
        with self.owned_service({'FSEARCH_FIXTURE_OPEN_DELAY_MS':'350'}) as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'deadline-old','query':'invoice'}
            with self.request(sock,query) as connection:before=self.receive(connection)
            worker=json.loads(Path(str(sock)+'.state').read_text())['worker']
            candidate_dir=work/'candidate';candidate_dir.mkdir();candidate=candidate_dir/'snapshot.db'
            shutil.copyfile(snapshot,candidate);candidate.chmod(0o600)
            replacement={'schema_version':1,'request_id':'deadline-candidate','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(candidate)).decode(),'timeout_ms':30}
            with self.request(sock,replacement) as connection:failed=self.receive(connection)
            self.assertEqual(failed.get('error',{}).get('code'),'deadline',failed)
            state=json.loads(Path(str(sock)+'.state').read_text())
            self.assertEqual(state['worker'],worker);self.assertIsNone(state['candidate_worker']);self.assertEqual(state['phase'],'ready')
            with self.request(sock,query) as connection:after=self.receive(connection)
            self.assertEqual(after['results'],before['results']);self.assertEqual(after['snapshot']['identity'],before['snapshot']['identity'])

    def test_replacement_keeps_old_queries_available_during_load_and_switches_identity(self):
        with self.owned_service({'FSEARCH_FIXTURE_OPEN_DELAY_MS':'350'}) as (work,root,snapshot,sock,server):
            query={'schema_version':1,'request_id':'snapshot-query','query':'pdf','kind':'files'}
            with self.request(sock,query) as connection:before=self.receive(connection)
            old=json.loads(Path(str(sock)+'.state').read_text())['worker']
            candidate_directory=work/'candidate';candidate_directory.mkdir();candidate=candidate_directory/'snapshot.db'
            replacement_root=work/'replacement-root';replacement_root.mkdir();(replacement_root/'new-report.pdf').touch()
            subprocess.run([FIXTURE,'build',str(candidate),str(replacement_root)],check=True,capture_output=True,timeout=5);candidate.chmod(0o600)
            shutil.rmtree(replacement_root);shutil.rmtree(root)
            request={'schema_version':1,'request_id':'replace-good','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(candidate)).decode(),'timeout_ms':2000}
            with self.request(sock,request) as replacing:
                deadline=time.monotonic()+1
                while time.monotonic()<deadline:
                    state=json.loads(Path(str(sock)+'.state').read_text())
                    if state.get('candidate_worker'):break
                    time.sleep(.005)
                self.assertIsNotNone(state.get('candidate_worker'),state)
                self.assertEqual(state['worker'],old)
                for record in (state['worker'],state['candidate_worker']):
                    line=next(line for line in Path(f"/proc/{record['pid']}/limits").read_text().splitlines() if line.startswith('Max address space'))
                    self.assertLessEqual(int(line.split()[3]),256*1024*1024)
                with self.request(sock,request) as overlap:rejected=self.receive(overlap)
                self.assertEqual(rejected.get('error',{}).get('code'),'replacement_busy')
                started=time.monotonic()
                with self.request(sock,query) as connection:during=self.receive(connection)
                self.assertLess(time.monotonic()-started,.2)
                self.assertEqual(during['results'],before['results']);self.assertEqual(during['snapshot']['identity'],before['snapshot']['identity'])
                accepted=self.receive(replacing)
            self.assertEqual(accepted['status'],'replaced',accepted)
            with self.request(sock,query) as connection:after=self.receive(connection)
            self.assertEqual([row['path'] for row in after['results']],[str(replacement_root/'new-report.pdf')])
            self.assertNotEqual(after['snapshot']['identity'],before['snapshot']['identity'])
            self.assertEqual(after['snapshot']['identity'],accepted['snapshot_id'])
            self.assertFalse(Path(f"/proc/{old['pid']}").exists(),'Old worker must be reaped before replacement acknowledgement')

    def test_unproved_retirement_blocks_replacement_until_explicit_recovery(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-retirement-fault-') as faults:
            blocked=Path(faults)/'block-waitpid'
            with self.owned_service({'FSEARCH_FIXTURE_WAITPID_BLOCK_FILE':str(blocked)}) as (work,root,snapshot,sock,server):
                with self.request(sock) as connection:self.receive(connection)
                candidate=work/'next.db';newroot=work/'next-root';newroot.mkdir();(newroot/'next-only.pdf').touch()
                subprocess.run([FIXTURE,'build',str(candidate),str(newroot)],check=True,capture_output=True,timeout=5);candidate.chmod(0o600)
                replacement={'schema_version':1,'request_id':'uncertain-retirement','op':'replace','candidate_database_b64':base64.b64encode(os.fsencode(candidate)).decode()}
                blocked.touch()
                try:
                    with self.request(sock,replacement) as connection:failed=self.receive(connection)
                    self.assertEqual(failed.get('error',{}).get('code'),'cleanup_unproved',failed)
                    state=json.loads(Path(str(sock)+'.state').read_text())
                    self.assertEqual(state['phase'],'quarantined');self.assertIsNotNone(state['retiring_worker']);self.assertIsNotNone(state['worker'])
                    with self.request(sock,replacement) as connection:denied=self.receive(connection)
                    self.assertEqual(denied.get('error',{}).get('code'),'quarantined')
                finally:blocked.unlink()
                time.sleep(.15);server.terminate();server.communicate(timeout=5)
                restart=subprocess.run([SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(restart.stdout)['error']['code'],'quarantined')
                recovered=subprocess.run([SERVICE,'recover','--socket',str(sock)],capture_output=True,text=True,timeout=5)
                self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
                try:
                    result=subprocess.run([CLI,'--socket',str(sock),'--database',str(snapshot),'--query','next-only'],capture_output=True,text=True,timeout=5)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertEqual([row['path'] for row in json.loads(result.stdout)['results']],[str(newroot/'next-only.pdf')])
                finally:self.stop_owned_service(sock)

    def test_repeated_unicode_queries_keep_resident_worker_memory_bounded(self):
        names=[f"ordinary-{i:04d}-"+"x"*80+".txt" for i in range(4096)]+['École.pdf']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            def search():
                with self.request(sock,{'schema_version':1,'request_id':'unicode-memory','query':'école','kind':'files'}) as connection:
                    payload=self.receive(connection)
                self.assertTrue(payload['complete'],payload)
                self.assertEqual([row['path'] for row in payload['results']],[str(root/'École.pdf')])
            for _ in range(5): search()
            initial=json.loads(Path(str(sock)+'.state').read_text())['worker']
            def rss():
                return int(next(line.split()[1] for line in Path(f"/proc/{initial['pid']}/status").read_text().splitlines() if line.startswith('VmRSS:')))
            before=rss()
            for _ in range(64): search()
            after=rss()
            self.assertEqual(json.loads(Path(str(sock)+'.state').read_text())['worker'],initial,'Repeated queries must reuse the same worker')
            self.assertLessEqual(after-before,4096,'Repeated Unicode searches must not accumulate per-entry filename copies')

    def test_selective_query_reaches_late_cached_name_with_small_verification_budget(self):
        names=[f"ordinary-{i:04d}.txt" for i in range(4096)]+['zz-only-target.pdf']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            with self.request(sock,{'schema_version':1,'request_id':'late-selective','query':'zz-only-target','kind':'files','max_candidates':2}) as connection:
                payload=self.receive(connection)
            self.assertTrue(payload['complete'],payload)
            self.assertEqual([row['path'] for row in payload['results']],[str(root/'zz-only-target.pdf')])

    def test_path_query_reaches_late_name_with_small_verification_budget(self):
        names=[f"ordinary-{i:04d}.txt" for i in range(4096)]+['zz-path-target.pdf']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            with self.request(sock,{'schema_version':1,'request_id':'path-candidate','query':'zz-path-target','path':True,'kind':'files','max_candidates':2}) as connection:
                payload=self.receive(connection)
            self.assertTrue(payload['complete'],payload)
            self.assertEqual([row['path'] for row in payload['results']],[str(root/'zz-path-target.pdf')])

    def test_unicode_query_skips_ascii_names_without_losing_casefold_matches(self):
        names=[f"ordinary-{i:04d}.txt" for i in range(4096)]+['École.pdf','Kelvin.txt']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            for query,name in [('école','École.pdf'),('Kelvin','Kelvin.txt')]:
                with self.request(sock,{'schema_version':1,'request_id':'unicode-candidate','query':query,'kind':'files','max_candidates':2}) as connection:
                    payload=self.receive(connection)
                self.assertTrue(payload['complete'],payload)
                self.assertEqual([row['path'] for row in payload['results']],[str(root/name)])

    def test_short_substring_reaches_late_name_with_small_verification_budget(self):
        names=[f"ordinary-{i:04d}.txt" for i in range(4096)]+['zz-ab.txt']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            with self.request(sock,{'schema_version':1,'request_id':'short-candidate','query':'ab','kind':'files','max_candidates':2}) as connection:
                payload=self.receive(connection)
            self.assertTrue(payload['complete'],payload)
            self.assertEqual([row['path'] for row in payload['results']],[str(root/'zz-ab.txt')])

    def test_unicode_corpus_selects_normalized_literal_candidates(self):
        names=[f"обычный-{i:04d}.txt" for i in range(4096)]+['学校-инвойс.pdf']
        with self.owned_service(names=names) as (work,root,snapshot,sock,server):
            with self.request(sock,{'schema_version':1,'request_id':'unicode-corpus','query':'学校','kind':'files','max_candidates':2}) as connection:
                payload=self.receive(connection)
            self.assertTrue(payload['complete'],payload)
            self.assertEqual([row['path'] for row in payload['results']],[str(root/'学校-инвойс.pdf')])

    def test_service_and_worker_address_space_are_bounded(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-limits-') as temporary:
            work=Path(temporary); root=work/'owned'; root.mkdir(); (root/'invoice.pdf').touch()
            snapshot=work/'snapshot.db'; sock=work/'search.sock'
            built=subprocess.run([FIXTURE,'build',str(snapshot),str(root)],capture_output=True,text=True,timeout=10)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            snapshot.chmod(0o600)
            try:
                result=subprocess.run([CLI,'--socket',str(sock),'--database',str(snapshot),'--query','invoice'],capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                state=json.loads((work/'search.sock.state').read_text())
                for key,ceiling in [('supervisor',64*1024*1024),('worker',256*1024*1024)]:
                    line=next(line for line in Path(f"/proc/{state[key]['pid']}/limits").read_text().splitlines() if line.startswith('Max address space'))
                    self.assertLessEqual(int(line.split()[3]),ceiling)
            finally:
                self.stop_owned_service(sock)
    def test_uncertain_cleanup_stays_quarantined_until_explicit_recovery(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-quarantine-') as temporary:
            work=Path(temporary); root=work/'owned'; root.mkdir(); (root/'invoice.pdf').touch()
            snapshot=work/'snapshot.db'; sock=work/'search.sock'; blocked=work/'block-waitpid'; blocked.touch()
            subprocess.run([FIXTURE,'build',str(snapshot),str(root)],check=True,capture_output=True,timeout=10); snapshot.chmod(0o600)
            armed=work/'arm-query-delay'
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_FIXTURE_AFTER_LOAD_DELAY_MS='250',FSEARCH_FIXTURE_QUERY_DELAY_MS='500',FSEARCH_FIXTURE_QUERY_DELAY_ARM_FILE=str(armed),FSEARCH_FIXTURE_WAITPID_BLOCK_FILE=str(blocked))
            server=subprocess.Popen([SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                for _ in range(200):
                    if sock.exists(): break
                    time.sleep(.01)
                # Prove a resident worker before testing active-query cleanup. A cold
                # 50ms request can correctly expire in the queue during worker load.
                warmed=subprocess.run([CLI,'--socket',str(sock),'--query','invoice','--timeout-ms','2000'],capture_output=True,text=True,timeout=5)
                self.assertEqual(warmed.returncode,0,warmed.stdout+warmed.stderr)
                resident=json.loads((work/'search.sock.state').read_text())['worker']
                self.assertIsNotNone(resident)
                armed.touch()
                result=subprocess.run([CLI,'--socket',str(sock),'--query','invoice','--timeout-ms','50'],capture_output=True,text=True,timeout=5)
                payload=json.loads(result.stdout)
                self.assertEqual(payload.get('error',{}).get('code'),'cleanup_unproved',result.stdout)
                state=json.loads((work/'search.sock.state').read_text()); self.assertEqual(state['phase'],'quarantined')
                self.assertEqual(state['worker'],resident)
                denied=subprocess.run([CLI,'--socket',str(sock),'--query','invoice'],capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(denied.stdout)['error']['code'],'quarantined')
                blocked.unlink()
                deadline=time.monotonic()+2
                while Path(f"/proc/{state['worker']['pid']}").exists() and time.monotonic()<deadline:time.sleep(.005)
                self.assertFalse(Path(f"/proc/{state['worker']['pid']}").exists(), 'quarantined supervisor must reap once evidence is available')
            finally:
                if blocked.exists(): blocked.unlink()
                server.terminate(); server.communicate(timeout=5)
            restart=subprocess.run([SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(restart.stdout)['error']['code'],'quarantined')
            recovered=subprocess.run([SERVICE,'recover','--socket',str(sock)],capture_output=True,text=True,timeout=5)
            self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
            try:
                ready=subprocess.run([CLI,'--socket',str(sock),'--database',str(snapshot),'--query','invoice'],capture_output=True,text=True,timeout=5)
                self.assertEqual(ready.returncode,0,ready.stdout+ready.stderr)
            finally:
                self.stop_owned_service(sock)
    @contextmanager
    def owned_service(self, injected=None, names=(), previous_boot=False):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-fixture-') as temporary:
            work=Path(temporary); root=work/'owned'; root.mkdir(); (root/'invoice.pdf').touch()
            for name in names: (root/name).touch()
            snapshot=work/'snapshot.db'; sock=work/'search.sock'
            subprocess.run([FIXTURE,'build',str(snapshot),str(root)],check=True,capture_output=True,timeout=10); snapshot.chmod(0o600)
            if previous_boot:
                record={'pid':os.getpid(),'start':'1','boot':str(uuid.uuid4())}
                state=Path(str(sock)+'.state')
                state.write_text(json.dumps({'phase':'ready','worker':record,'supervisor':record,'database':str(snapshot)}));state.chmod(0o600)
            env=dict(os.environ)
            if injected: env.update(LD_PRELOAD=FAULT,**injected)
            server=subprocess.Popen([SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                for _ in range(200):
                    if sock.exists(): break
                    if server.poll() is not None: self.fail(server.communicate())
                    time.sleep(.01)
                self.assertTrue(sock.exists())
                yield work,root,snapshot,sock,server
            finally:
                if server.poll() is None: server.terminate()
                server.communicate(timeout=5)
    def request(self, sock, request=None):
        until=time.monotonic()+4
        while True:
            connection=socket.socket(socket.AF_UNIX); connection.settimeout(4)
            try: connection.connect(str(sock)); break
            except (ConnectionRefusedError,FileNotFoundError):
                connection.close()
                if time.monotonic()>=until: raise
                time.sleep(.005)
        connection.sendall((json.dumps(request or {'schema_version':1,'request_id':'fixture','query':'invoice'})+'\n').encode())
        return connection
    def receive(self, connection):
        result=bytearray()
        while b'\n' not in result:
            chunk=connection.recv(65536)
            self.assertTrue(chunk,'service closed before a structured response'); result.extend(chunk)
        return json.loads(result)
    def test_malformed_frames_fail_without_crashing_service(self):
        with self.owned_service() as (_,_,_,sock,_):
            for raw in (b'{broken}\n',b'[]\n',b'x'*65537,b'{"schema_version":true,"request_id":"bad","query":"invoice"}\n'):
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(4); connection.connect(str(sock)); connection.sendall(raw)
                    payload=self.receive(connection); self.assertEqual(payload['error']['code'],'invalid_request')
                with self.request(sock) as connection: self.assertTrue(self.receive(connection)['complete'])
    def test_queue_is_bounded_and_deadline_includes_waiting(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-delay-') as temporary:
            marker=Path(temporary)/'started'
            with self.owned_service({'FSEARCH_FIXTURE_QUERY_DELAY_MS':'500','FSEARCH_FIXTURE_MARKER':str(marker)}) as (_,_,_,sock,_):
                connections=[]
                try:
                    first=self.request(sock); connections.append(first)
                    for _ in range(200):
                        if marker.exists(): break
                        time.sleep(.005)
                    self.assertTrue(marker.exists())
                    for i in range(8):
                        c=self.request(sock,{'schema_version':1,'request_id':str(i),'query':'invoice','timeout_ms':50 if i==0 else 2000}); connections.append(c)
                    busy=self.request(sock); connections.append(busy)
                    self.assertEqual(self.receive(busy)['error']['code'],'busy')
                    self.assertEqual(self.receive(connections[1])['error']['code'],'deadline')
                    self.assertTrue(self.receive(first)['complete'])
                    for c in connections[2:9]: self.assertTrue(self.receive(c)['complete'])
                finally:
                    for c in connections: c.close()
    def test_stop_acknowledges_shutdown_and_reaps_worker(self):
        with self.owned_service() as (work,_,_,sock,server):
            with self.request(sock) as connection: self.assertTrue(self.receive(connection)['complete'])
            state=json.loads((work/'search.sock.state').read_text())
            stopped=subprocess.run([SERVICE,'stop','--socket',str(sock)],capture_output=True,text=True,timeout=5)
            self.assertEqual(stopped.returncode,0,stopped.stdout+stopped.stderr)
            server.wait(timeout=5)
            self.assertFalse(Path(f"/proc/{state['worker']['pid']}").exists())
    def test_recovery_cannot_treat_missing_identity_as_absence(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-recovery-') as temporary:
            work=Path(temporary); sock=work/'search.sock'; state=work/'search.sock.state'
            state.write_text(json.dumps({'phase':'quarantined','worker':{'pid':os.getpid()}})); state.chmod(0o600)
            result=subprocess.run([SERVICE,'recover','--socket',str(sock)],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(json.loads(state.read_text())['phase'],'quarantined')
    def test_disconnected_active_request_reaps_worker_without_replay(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-cancel-') as temporary:
            marker=Path(temporary)/'started'
            with self.owned_service({'FSEARCH_FIXTURE_QUERY_DELAY_MS':'500','FSEARCH_FIXTURE_MARKER':str(marker)}) as (work,_,_,sock,_):
                connection=self.request(sock)
                for _ in range(200):
                    if marker.exists(): break
                    time.sleep(.005)
                self.assertTrue(marker.exists()); worker=int(marker.read_text()); connection.close()
                for _ in range(100):
                    if not Path(f'/proc/{worker}').exists(): break
                    time.sleep(.005)
                self.assertFalse(Path(f'/proc/{worker}').exists())
                for _ in range(100):
                    state=json.loads((work/'search.sock.state').read_text())
                    if state['phase']=='stopped': break
                    time.sleep(.005)
                self.assertEqual(state['phase'],'stopped'); self.assertEqual(state['reason'],'cancelled')
                with self.request(sock,{'schema_version':1,'request_id':'fresh','query':'invoice','timeout_ms':5000}) as fresh:
                    result=self.receive(fresh); self.assertTrue(result['complete'],result)
    def test_startup_deadline_reaps_worker_and_never_scans(self):
        with self.owned_service({'FSEARCH_FIXTURE_OPEN_DELAY_MS':'5000'}) as (work,_,_,sock,_):
            started=time.monotonic()
            with self.request(sock,{'schema_version':1,'request_id':'load','query':'invoice','timeout_ms':10000}) as connection:
                payload=self.receive(connection)
            self.assertEqual(payload['error']['code'],'startup_deadline')
            self.assertLess(time.monotonic()-started,2.8)
            state=json.loads((work/'search.sock.state').read_text()); self.assertEqual(state['phase'],'stopped'); self.assertIsNone(state['worker'])
    def test_worker_crash_fails_request_and_new_request_can_restart(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-crash-') as temporary:
            marker=Path(temporary)/'started'
            with self.owned_service({'FSEARCH_FIXTURE_QUERY_DELAY_MS':'500','FSEARCH_FIXTURE_MARKER':str(marker)}) as (_,_,_,sock,_):
                with self.request(sock) as connection:
                    for _ in range(200):
                        if marker.exists(): break
                        time.sleep(.005)
                    self.assertTrue(marker.exists()); os.kill(int(marker.read_text()),signal.SIGKILL)
                    self.assertEqual(self.receive(connection)['error']['code'],'worker_failed')
                with self.request(sock,{'schema_version':1,'request_id':'fresh','query':'invoice','timeout_ms':5000}) as fresh:
                    result=self.receive(fresh); self.assertTrue(result['complete'],result)
    @unittest.skipUnless(shutil.which('strace'),'strace required for indexed-root isolation evidence')
    def test_idle_and_warm_queries_do_not_probe_removed_indexed_root(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-trace-') as temporary:
            work=Path(temporary); root=work/'owned'; root.mkdir(); (root/'contenttype:pdf-invoice.pdf').touch()
            snapshot=work/'snapshot.db'; sock=work/'search.sock'; trace=work/'service.trace'
            subprocess.run([FIXTURE,'build',str(snapshot),str(root)],check=True,capture_output=True,timeout=10); snapshot.chmod(0o600)
            (root/'contenttype:pdf-invoice.pdf').unlink(); root.rmdir()
            server=subprocess.Popen(['strace','-f','-e','trace=%file','-o',str(trace),SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                for _ in range(200):
                    if sock.exists(): break
                    time.sleep(.01)
                for i in range(2):
                    if i: time.sleep(6)
                    with self.request(sock,{'schema_version':1,'request_id':str(i),'query':'contenttype:'}) as connection:
                        payload=self.receive(connection); self.assertTrue(payload['complete']); self.assertEqual(len(payload['results']),1)
                stopped=subprocess.run([SERVICE,'stop','--socket',str(sock)],capture_output=True,timeout=5)
                self.assertEqual(stopped.returncode,0)
                server.communicate(timeout=5)
                self.assertNotIn(str(root),trace.read_text())
            finally:
                if server.poll() is None:
                    os.killpg(server.pid,signal.SIGTERM)
                    try: server.communicate(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(server.pid,signal.SIGKILL); server.communicate(timeout=5)
    def test_supervisor_crash_requires_reconciliation_before_restart(self):
        with self.owned_service() as (work,_,snapshot,sock,server):
            with self.request(sock) as connection: self.assertTrue(self.receive(connection)['complete'])
            state=json.loads((work/'search.sock.state').read_text()); worker=state['worker']['pid']
            server.kill(); server.wait(timeout=5)
            for _ in range(200):
                pid,_=os.waitpid(worker,os.WNOHANG)
                if pid==worker: break
                time.sleep(.005)
            self.assertEqual(pid,worker,'parent-death signal must terminate the resident worker')
            denied=subprocess.run([SERVICE,'serve','--socket',str(sock),'--database',str(snapshot)],capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(denied.stdout)['error']['code'],'quarantined')
            recovered=subprocess.run([SERVICE,'recover','--socket',str(sock)],capture_output=True,text=True,timeout=5)
            self.assertEqual(recovered.returncode,0,recovered.stdout)
    def test_client_cannot_silently_retarget_an_existing_service_snapshot(self):
        with self.owned_service() as (_,_,snapshot,sock,_):
            with self.request(sock) as connection: self.assertTrue(self.receive(connection)['complete'])
            other=snapshot.with_name('different.db'); other.write_bytes(snapshot.read_bytes()); other.chmod(0o600)
            result=subprocess.run([CLI,'--socket',str(sock),'--database',str(other),'--query','invoice'],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(json.loads(result.stdout)['error']['code'],'snapshot_conflict')
    def test_socket_client_preserves_maximum_literal_query_input(self):
        with self.owned_service() as (_,_,_,sock,_):
            result=subprocess.run([CLI,'--socket',str(sock),'--query','\n'*4096],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(json.loads(result.stdout)['complete'])
    def test_private_socket_guards_preserve_unrelated_paths(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-service-private-') as temporary:
            work=Path(temporary); sock=work/'search.sock'; sock.write_text('preserve me'); sock.chmod(0o600)
            denied=subprocess.run([SERVICE,'serve','--socket',str(sock),'--database',str(work/'missing.db')],capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(denied.stdout)['error']['code'],'unsafe_socket'); self.assertEqual(sock.read_text(),'preserve me')
            sock.unlink(); sock.symlink_to(work/'target')
            denied=subprocess.run([SERVICE,'serve','--socket',str(sock),'--database',str(work/'missing.db')],capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(denied.stdout)['error']['code'],'unsafe_socket'); self.assertTrue(sock.is_symlink())
            sock.unlink(); work.chmod(0o755)
            denied=subprocess.run([SERVICE,'query','--socket',str(sock),'--query','invoice'],capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(denied.stdout)['error']['code'],'unsafe_directory'); work.chmod(0o700)
    def test_fixed_snapshot_remains_searchable_after_snapshot_file_disappears(self):
        with self.owned_service() as (_,_,snapshot,sock,_):
            with self.request(sock) as connection: first=self.receive(connection); self.assertTrue(first['complete'])
            snapshot.unlink()
            with self.request(sock) as connection: second=self.receive(connection); self.assertTrue(second['complete'])
            self.assertEqual(first['results'],second['results']); self.assertEqual(first['snapshot']['identity'],second['snapshot']['identity'])
    def test_missing_snapshot_is_explicit_and_does_not_fall_back_to_scan(self):
        with self.owned_service() as (_,_,snapshot,sock,_):
            snapshot.unlink()
            with self.request(sock) as connection: self.assertEqual(self.receive(connection)['error']['code'],'snapshot_unavailable')
    def test_maximum_response_bytes_include_escaped_request_identity(self):
        with self.owned_service() as (_,_,_,sock,_):
            with self.request(sock,{'schema_version':1,'request_id':'\x01'*64,'query':'invoice','max_bytes':512}) as connection:
                raw=bytearray()
                while b'\n' not in raw:
                    chunk=connection.recv(4096); self.assertTrue(chunk); raw.extend(chunk)
                self.assertLessEqual(len(raw),512)
                self.assertFalse(json.loads(raw)['complete'])
    def test_empty_literal_extension_matches_direct_cli_semantics(self):
        with self.owned_service() as (_,_,snapshot,sock,_):
            direct=subprocess.run([CLI,'--database',str(snapshot),'--query','invoice','--extension',''],capture_output=True,text=True,timeout=5)
            warm=subprocess.run([CLI,'--socket',str(sock),'--query','invoice','--extension',''],capture_output=True,text=True,timeout=5)
            self.assertEqual(direct.returncode,0,direct.stdout); self.assertEqual(warm.returncode,0,warm.stdout)
            self.assertEqual(json.loads(warm.stdout)['results'],json.loads(direct.stdout)['results'])
if __name__=='__main__': unittest.main(argv=[sys.argv[0],*sys.argv[5:]])
