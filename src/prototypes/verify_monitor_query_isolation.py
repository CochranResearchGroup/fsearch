"""Owned monitor/query isolation acceptance; never admit production roots."""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time


def reply(process):
    data = bytearray(); deadline = time.monotonic()+5
    while time.monotonic() < deadline:
        if not select.select([process.stdout], [], [], .05)[0]: continue
        byte = os.read(process.stdout.fileno(), 1)
        if not byte: raise RuntimeError('unexpected monitor EOF')
        data.extend(byte)
        if byte == b'\n': return json.loads(data)
    raise RuntimeError('monitor reply deadline')


def until(process, status):
    for _ in range(24):
        message = reply(process)
        if message['status'] == status: return message
        if message['status'] == 'error': raise RuntimeError(message)
    raise RuntimeError('monitor reconciliation bound')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, default=Path('/tmp/fsearch-warm-release-build/src'))
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args(); runtime = args.runtime.resolve(); evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fsearch-monitor-query-owned-') as temporary:
        work = Path(temporary); root = work/'approved'; root.mkdir(); (root/'invoice.pdf').touch()
        database = work/'accepted.db'; socket = work/'query.sock'; monitor = server = None
        command = ['python3', str(runtime/'fsearch-monitor'), 'watch', '--root', str(root), '--database', str(database)]
        receipt = {'owned_fixtures_only': True, 'runtime': str(runtime), 'queries': []}
        def start(extra=()):
            return subprocess.Popen([*command, *extra], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def query(label):
            trace = evidence/(label+'.trace')
            result = subprocess.run(['strace', '-f', '-yy', '-e', 'trace=%file,getdents64', '-o', str(trace),
                                     str(runtime/'fsearch-cli'), '--socket', str(socket), '--query', 'invoice', '--kind', 'files'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode: raise RuntimeError(result.stdout+result.stderr)
            payload = json.loads(result.stdout); receipt['queries'].append({'label': label, 'response': payload})
            return payload
        try:
            monitor = start(); until(monitor, 'published'); monitor.terminate(); monitor.wait(timeout=3)
            monitor.stdout.close(); monitor.stderr.close(); monitor = None
            server = subprocess.Popen(['strace', '-f', '-yy', '-e', 'trace=%file,getdents64', '-o', str(evidence/'query-service.trace'),
                                       'python3', str(runtime/'fsearch-service'), 'serve', '--socket', str(socket), '--database', str(database)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic()+3
            while not socket.exists() and time.monotonic() < deadline: time.sleep(.005)
            initial = query('before-monitor')
            monitor = start(['--socket', str(socket)]); until(monitor, 'published'); first_ack = until(monitor, 'serving_replaced')
            (root/'invoice-new.pdf').touch(); until(monitor, 'published'); second_ack = until(monitor, 'serving_replaced')
            refreshed = query('while-monitoring'); assert len(refreshed['results']) == 2
            assert refreshed['snapshot']['identity'] == second_ack['snapshot_id']
            assert initial['snapshot']['identity'] != first_ack['snapshot_id']
            root.rename(work/'offline'); failure = reply(monitor)
            assert failure['error']['code'] == 'root_offline', failure
            assert monitor.wait(timeout=3) != 0
            time.sleep(1)  # Observe idle serving beyond the former polling interval.
            offline = query('after-root-removal'); assert offline['results'] == refreshed['results']
            assert offline['snapshot']['identity'] == second_ack['snapshot_id']
            receipt['offline_failure'] = failure
        finally:
            if monitor:
                if monitor.poll() is None: monitor.terminate()
                monitor.wait(timeout=3); monitor.stdout.close(); monitor.stderr.close()
            if server:
                stopped = subprocess.run(['python3', str(runtime/'fsearch-service'), 'stop', '--socket', str(socket)],
                                         capture_output=True, text=True, timeout=4)
                if stopped.returncode: raise RuntimeError('owned service shutdown failed: '+stopped.stdout)
                assert server.wait(timeout=4) == 0
                server.stdout.close(); server.stderr.close()
        traces = [evidence/(label+'.trace') for label in ('before-monitor', 'while-monitoring', 'after-root-removal', 'query-service')]
        assert all(str(root) not in trace.read_text() for trace in traces)
        control = evidence/'root-probe-negative-control.trace'
        subprocess.run(['strace', '-f', '-e', 'trace=%file', '-o', str(control), 'stat', str(root)], capture_output=True)
        assert str(root) in control.read_text()
        receipt.update({'all_query_process_root_probes': 0, 'negative_control_detected': True, 'service_exit': 0})
        (evidence/'query-isolation.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print('Monitor refresh/replacement and all-process query isolation passed')


if __name__ == '__main__': main()
