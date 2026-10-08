"""Public refresh worker tests using only owned roots and snapshots."""
import ctypes,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
WORKER=Path(sys.argv.pop(1));CLI=Path(sys.argv.pop(1));REFRESH=WORKER.with_name("fsearch-refresh");FAULT=sys.argv.pop(1)
SNAPSHOT_FAULT=sys.argv.pop(1)
ctypes.CDLL(None).prctl(36,1,0,0,0)  # Own orphaned fault-fixture workers.
class RefreshWorker(unittest.TestCase):
    def test_permission_exclusion_is_reported_without_losing_readable_siblings(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-permission-') as temporary:
            root=Path(temporary)/'root';root.mkdir();(root/'unreadable').mkdir();(root/'visible.pdf').touch()
            database=Path(temporary)/'snapshot.db'
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_PERMISSION='1')
            result=subprocess.run(['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)],env=env,capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['scan']['excluded_permissions'],1)
            query=subprocess.run([str(CLI),'--database',str(database),'--query','visible.pdf'],capture_output=True,text=True,timeout=5)
            self.assertEqual(query.returncode,0,query.stdout+query.stderr)
            self.assertEqual(len(json.loads(query.stdout)['results']),1)

    def test_malformed_worker_reply_is_structured_and_preserves_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-protocol-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr);before=database.read_bytes()
            for variant in ('1','ready','error'):
                env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_INVALID_REPLY=variant)
                failed=subprocess.run(command,env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(failed.stdout)['error']['code'],'worker_protocol_failed',failed.stdout+failed.stderr)
                self.assertNotIn('Traceback',failed.stderr);self.assertEqual(database.read_bytes(),before)
    def tearDown(self):
        for _ in range(100):
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if pid==0:time.sleep(.005)
            except ChildProcessError:break
    def test_worker_eof_without_exit_returns_deadline_and_preserves_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-eof-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr);before=database.read_bytes()
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='500',FSEARCH_REFRESH_FIXTURE_CLOSE_STDOUT='1')
            failed=subprocess.run([*command,'--timeout-ms','30'],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(failed.stdout)['error']['code'],'deadline',failed.stdout+failed.stderr)
            self.assertNotIn('Traceback',failed.stderr)
            self.assertEqual(database.read_bytes(),before)
            state=json.loads(Path(str(database)+'.refresh.state').read_text())
            self.assertEqual(state['phase'],'stopped');self.assertIsNone(state['worker'])
    def test_supervisor_shutdown_before_worker_main_proves_absence(self):
        import signal
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-loader-shutdown-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();database=work/'accepted.db'
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_STOP_BEFORE_MAIN='1')
            process=subprocess.Popen(['python3',str(REFRESH),'refresh','--root',str(root),
                '--database',str(database)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            worker=None
            try:
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    try:
                        state=json.loads(Path(str(database)+'.refresh.state').read_text())
                        worker=(state.get('worker') or {}).get('pid')
                        if worker and any(line.startswith('State:') and 'T' in line.split()[1]
                            for line in Path('/proc',str(worker),'status').read_text().splitlines()):break
                    except (OSError,ValueError):pass
                    time.sleep(.005)
                else:self.fail('fixture never stopped before native main')
                process.terminate();process.communicate(timeout=3)
                deadline=time.monotonic()+1
                while time.monotonic()<deadline:
                    try:reaped,_=os.waitpid(worker,os.WNOHANG)
                    except ChildProcessError:break
                    if reaped:break
                    time.sleep(.005)
                self.assertFalse(Path('/proc',str(worker)).exists(),'pre-main worker survived parent shutdown')
                self.assertFalse(database.exists())
            finally:
                if process.poll() is None:process.kill()
                process.communicate(timeout=3)
                if worker:
                    try:os.kill(worker,signal.SIGKILL)
                    except ProcessLookupError:pass
                    try:os.waitpid(worker,0)
                    except ChildProcessError:pass
    def test_supervisor_shutdown_preserves_snapshot_and_requires_recovery(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-shutdown-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr);before=database.read_bytes()
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='2000')
            process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            state_path=Path(str(database)+'.refresh.state');worker=None
            try:
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    state=json.loads(state_path.read_text())
                    if state['phase']=='starting':worker=state['worker']['pid'];break
                    time.sleep(.005)
                else:self.fail('refresh never recorded worker identity')
                process.terminate();process.communicate(timeout=5)
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    try:reaped,_=os.waitpid(worker,os.WNOHANG)
                    except ChildProcessError:break
                    if reaped:break
                    time.sleep(.005)
                else:self.fail('worker survived supervisor shutdown')
                self.assertFalse(Path('/proc',str(worker)).exists())
                self.assertEqual(database.read_bytes(),before)
                retry=subprocess.run(command,capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(retry.stdout)['error']['code'],'quarantined')
                recovered=subprocess.run(['python3',str(REFRESH),'recover','--database',str(database)],capture_output=True,text=True,timeout=5)
                self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
                self.assertEqual(database.read_bytes(),before)
            finally:
                if process.poll() is None:process.kill()
                process.communicate(timeout=5)
    def test_unproved_cleanup_requires_explicit_recovery_after_worker_absence(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-quarantine-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr);before=database.read_bytes()
            blocked=work/'blocked';blocked.touch()
            env=dict(os.environ,LD_PRELOAD=SNAPSHOT_FAULT,FSEARCH_FIXTURE_WAITPID_BLOCK_FILE=str(blocked))
            failed=subprocess.run([*command,'--timeout-ms','100'],env=env,capture_output=True,text=True,timeout=8)
            self.assertEqual(json.loads(failed.stdout)['error']['code'],'cleanup_unproved')
            state_path=Path(str(database)+'.refresh.state');state=json.loads(state_path.read_text())
            self.assertEqual(state['phase'],'quarantined');worker=state['worker']['pid']
            blocked.unlink()
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                try:reaped,_=os.waitpid(worker,os.WNOHANG)
                except ChildProcessError:break
                if reaped:break
                time.sleep(.005)
            else:self.fail('fixture worker was not reaped')
            retry=subprocess.run(command,capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(retry.stdout)['error']['code'],'quarantined')
            self.assertEqual(database.read_bytes(),before)
            recovered=subprocess.run(['python3',str(REFRESH),'recover','--database',str(database)],capture_output=True,text=True,timeout=5)
            self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
            self.assertEqual(json.loads(state_path.read_text())['phase'],'stopped')
            self.assertEqual(database.read_bytes(),before)
    def test_candidate_changed_after_validation_preserves_accepted_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-mutation-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr)
            before=database.read_bytes();replacement=work/'replacement.db';replacement.write_bytes(before);replacement.chmod(0o600)
            (root/'next.pdf').touch()
            env=dict(os.environ,LD_PRELOAD=SNAPSHOT_FAULT,FSEARCH_FIXTURE_REPLACE_WITH=str(replacement))
            failed=subprocess.run(command,env=env,capture_output=True,text=True,timeout=8)
            self.assertEqual(json.loads(failed.stdout)['error']['code'],'candidate_changed',failed.stdout+failed.stderr)
            self.assertFalse(replacement.exists(),'mutation adapter did not execute')
            self.assertEqual(database.read_bytes(),before)
            found=subprocess.run([str(CLI),'--database',str(database),'--query','invoice'],capture_output=True,text=True,timeout=5)
            self.assertEqual([row['path'] for row in json.loads(found.stdout)['results']],[str(root/'invoice.pdf')])
    def test_refresh_requires_explicit_absolute_root(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-explicit-') as temporary:
            database=Path(temporary)/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--database',str(database)]
            for arguments in ([],['--root','relative-root']):
                result=subprocess.run([*command,*arguments],capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(result.stdout)['error']['code'],'invalid_request')
                self.assertFalse(database.exists())
                self.assertFalse(Path(str(database)+'.refresh.state').exists())
    def test_concurrent_refresh_is_rejected_without_replacing_accepted_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-lock-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr)
            before=database.read_bytes();state_path=Path(str(database)+'.refresh.state')
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='1000')
            first=subprocess.Popen([*command,'--timeout-ms','300'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    if json.loads(state_path.read_text())['phase']=='starting':break
                    time.sleep(.005)
                else:self.fail('refresh never reached its durable starting state')
                state=json.loads(state_path.read_text())
                for pid,ceiling in ((first.pid,64*1024*1024),(state['worker']['pid'],2048*1024*1024)):
                    limits=Path('/proc',str(pid),'limits').read_text().splitlines()
                    address=next(line for line in limits if line.startswith('Max address space'))
                    self.assertLessEqual(int(address.split()[3]),ceiling)
                second=subprocess.run(command,capture_output=True,text=True,timeout=5)
                self.assertEqual(json.loads(second.stdout)['error']['code'],'already_running')
                self.assertEqual(database.read_bytes(),before)
                output,error=first.communicate(timeout=5)
                self.assertEqual(json.loads(output)['error']['code'],'deadline',error)
                self.assertEqual(database.read_bytes(),before)
                self.assertEqual(json.loads(state_path.read_text())['phase'],'stopped')
            finally:
                if first.poll() is None:first.kill()
                first.communicate(timeout=5)
    def test_owned_root_produces_searchable_candidate_without_following_symlink(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-owned-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();outside=work/'excluded';outside.mkdir()
            (root/'invoice.pdf').touch();(outside/'secret.pdf').touch();(root/'redirection').symlink_to(outside,target_is_directory=True)
            stage=work/'stage';stage.mkdir(mode=0o700);candidate=stage/'candidate.db'
            trace=work/'scan.trace'
            result=subprocess.run(['strace','-f','-yy','-e','trace=%file,fstat,getdents64','-o',str(trace),str(WORKER),'--root',str(root),'--output',str(candidate)],input='G',capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            calls=trace.read_text();self.assertIn('ELOOP',calls);self.assertNotIn(str(outside),calls);self.assertNotIn('secret.pdf',calls)
            receipt=json.loads(result.stdout);self.assertEqual(receipt['excluded_symlinks'],1)
            found=subprocess.run([str(CLI),'--database',str(candidate),'--query','pdf','--kind','files'],capture_output=True,text=True,timeout=5)
            self.assertEqual(found.returncode,0,found.stdout+found.stderr)
            self.assertEqual([row['path'] for row in json.loads(found.stdout)['results']],[str(root/'invoice.pdf')])
    def test_failed_refresh_preserves_last_accepted_results(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-lifecycle-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            initial=subprocess.run(['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)],capture_output=True,text=True,timeout=8)
            self.assertEqual(initial.returncode,0,initial.stdout+initial.stderr)
            before=database.read_bytes()
            failed=subprocess.run(['python3',str(REFRESH),'refresh','--root',str(work/'missing-root'),'--database',str(database)],capture_output=True,text=True,timeout=8)
            self.assertNotEqual(failed.returncode,0)
            self.assertEqual(database.read_bytes(),before)
            found=subprocess.run([str(CLI),'--database',str(database),'--query','invoice'],capture_output=True,text=True,timeout=5)
            self.assertEqual([row['path'] for row in json.loads(found.stdout)['results']],[str(root/'invoice.pdf')])

    def test_mount_boundary_adapter_rejects_before_metadata_and_omits_descendants(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-boundary-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch()
            excluded=root/'excluded-mount';excluded.mkdir();(excluded/'forbidden.pdf').touch()
            stage=work/'stage';stage.mkdir(mode=0o700);candidate=stage/'candidate.db'
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_MOUNT='1')
            result=subprocess.run([str(WORKER),'--root',str(root),'--output',str(candidate)],input='G',env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('injected_EXDEV',result.stderr);self.assertNotIn('FORBIDDEN_METADATA',result.stderr)
            self.assertEqual(json.loads(result.stdout)['excluded_mounts'],1)
            found=subprocess.run([str(CLI),'--database',str(candidate),'--query','pdf','--kind','files'],capture_output=True,text=True,timeout=5)
            self.assertEqual([row['path'] for row in json.loads(found.stdout)['results']],[str(root/'invoice.pdf')])

    def test_interrupted_refresh_preserves_accepted_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-deadline-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();(root/'invoice.pdf').touch();database=work/'accepted.db'
            command=['python3',str(REFRESH),'refresh','--root',str(root),'--database',str(database)]
            initial=subprocess.run(command,capture_output=True,text=True,timeout=8);self.assertEqual(initial.returncode,0,initial.stdout)
            before=database.read_bytes();(root/'next.pdf').touch()
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_ROOT_DELAY_MS='500')
            failed=subprocess.run([*command,'--timeout-ms','30'],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(failed.stdout)['error']['code'],'deadline')
            self.assertEqual(database.read_bytes(),before)
            state=json.loads(Path(str(database)+'.refresh.state').read_text());self.assertEqual(state['phase'],'stopped');self.assertIsNone(state['worker'])

    def test_unavailable_confinement_rejects_before_root_open(self):
        with tempfile.TemporaryDirectory(prefix='fsearch-refresh-no-confinement-') as temporary:
            work=Path(temporary);root=work/'approved';root.mkdir();stage=work/'stage';stage.mkdir(mode=0o700);trace=work/'denied.trace'
            env=dict(os.environ,LD_PRELOAD=FAULT,FSEARCH_REFRESH_FIXTURE_NO_LANDLOCK='1')
            result=subprocess.run(['strace','-f','-e','trace=openat2','-s','4096','-o',str(trace),str(WORKER),'--root',str(root),'--output',str(stage/'candidate.db')],input='G',env=env,capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(any('openat2(' in line and str(root) in line for line in trace.read_text().splitlines()),trace.read_text())
            self.assertFalse((stage/'candidate.db').exists())

if __name__=='__main__':unittest.main()
