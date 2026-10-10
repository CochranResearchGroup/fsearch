"""Boot-proof lifecycle boundary; synthetic private state, no root traversal."""
import importlib.util, json, os, sys, tempfile, unittest, uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location('lifecycle', Path(__file__).parents[1]/'fsearch_service.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)

class BootRecovery(unittest.TestCase):
    def test_startup_override_remains_bounded_and_default_is_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(lifecycle.worker_startup_timeout(), 2)
        for value, expected in [('1',.001),('30000',30)]:
            with patch.dict(os.environ, FSEARCH_WORKER_STARTUP_TIMEOUT_MS=value):
                self.assertEqual(lifecycle.worker_startup_timeout(), expected)
        for value in ('0','30001','invalid'):
            with patch.dict(os.environ, FSEARCH_WORKER_STARTUP_TIMEOUT_MS=value):
                with self.assertRaises(lifecycle.BoundaryError): lifecycle.worker_startup_timeout()

    def generation(self):
        record = lifecycle.identity(os.getpid())
        record['boot'] = str(uuid.uuid4())
        return {'phase':'ready','worker':dict(record),'supervisor':dict(record),
                'database':'accepted.db','accepted_database':'accepted.db','snapshot_id':'accepted'}

    def reconcile(self, state):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'query.sock.state'
            path.write_text(json.dumps(state)); path.chmod(0o600)
            directory = lifecycle.PrivateDirectory(str(Path(folder)/'query.sock'))
            directory.lock()
            try:
                lifecycle.reconcile(directory)
                return json.loads(path.read_text())
            finally: directory.close()

    def test_previous_boot_recovers_every_worker_phase_and_preserves_snapshot(self):
        for phase in ('ready','starting','quarantined'):
            with self.subTest(phase=phase):
                state = self.generation(); state['phase'] = phase
                state['candidate_worker'] = dict(state['worker'])
                state['retiring_worker'] = dict(state['worker'])
                result = self.reconcile(state)
                self.assertEqual(result['phase'],'stopped')
                self.assertEqual(result['reason'],'previous_boot_recovery')
                self.assertEqual(result['snapshot_id'],'accepted')
                self.assertEqual(result['accepted_database'],'accepted.db')
                self.assertIsNone(result['worker'])
                self.assertNotIn('candidate_worker',result)
                self.assertNotIn('retiring_worker',result)

    def test_uncertain_or_current_generation_remains_quarantined(self):
        states = []
        state=self.generation();state['supervisor']=lifecycle.identity(os.getpid());states.append(state)
        state=self.generation();state['worker']=lifecycle.identity(os.getpid());states.append(state)
        state=self.generation();state['candidate_worker']={'pid':os.getpid()};states.append(state)
        state=self.generation();state['retiring_worker']=dict(state['worker'],boot=str(uuid.uuid4()));states.append(state)
        state=self.generation();state.pop('supervisor');states.append(state)
        state=self.generation();state['worker']=None;states.append(state)
        state=self.generation();state['worker']['start']='01';states.append(state)
        for state in states:
            with self.subTest(state=state), self.assertRaises(lifecycle.BoundaryError):self.reconcile(state)

    def test_unknown_current_boot_does_not_authorize_recovery(self):
        state=self.generation()
        original=Path.read_text
        def read(path,*args,**kwargs):
            if str(path)=='/proc/sys/kernel/random/boot_id':raise PermissionError('boot unavailable')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',read), self.assertRaises(lifecycle.BoundaryError):self.reconcile(state)

if __name__ == '__main__':unittest.main()
