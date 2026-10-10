# Repository-owned privileged setup helper

This package installs the existing `src/fsearch_broker_setup.c` executable into a
SHA256-versioned root-owned directory. A root-created systemd SOCK_SEQPACKET
listener remains available across reader restarts. Only the short-lived setup
process receives CAP_SYS_ADMIN; it creates one filesystem-wide notification
source, transfers the descriptor to the authorized reader, and exits. No file
capabilities, setuid executable, general sudo rule, shell command endpoint or
privileged reader is installed. Setup failures are limited to three attempts per
minute; restarting the reader does not grant it capabilities.

The fixed root-owned config binds one UID and one admitted root. The prepared
bundle binds UID/GID1000 to the small owned qualification fixture, **not the real
workspace**. Its event observation is nevertheless filesystem-wide. Root changes
and helper upgrades require administrator maintenance. Install refuses existing
files or loaded units instead of overwriting them; removal refuses content drift.
For upgrades, stop the reader, remove the reconciled old package, then install the
new version. There is no unattended upgrade or automatic capability escalation.

## Prepared installation

From `/home/ecochran76/worktrees/fsearch-incremental-generations`:

```sh
sudo /usr/bin/python3 packaging/broker/manage.py install \
  --bundle /home/ecochran76/worktrees/fsearch-broker-helper-bundle --listen
```

This is the new command; do not run the old temporary activation coordinator
against an installed helper. Installation copies/seals the four manifest files,
records `/usr/local/libexec/fsearch-broker/installation.json`, reloads systemd,
and enables/starts only the socket. No filesystem mark exists until a reader
connects. Normal unprivileged reader/test launches then use
`--handoff-socket /run/fsearch/broker.sock`, without sudo. This helper installation
does not install the continuous reader, switch the existing snapshot service,
qualify actual delivery, or complete M3–M6. Actual test execution still uses its
bounded pressure guard, and requires a fresh cleanup/process readback afterward.

## Rollback

Stop/reap the unprivileged reader first; it holds the event descriptor and mark.
Then:

```sh
sudo /usr/bin/python3 packaging/broker/manage.py remove
```

Removal checks installed file hashes before effects, disables/stops the socket,
stops setup, removes only receipt-bound files, preserves nonempty shared
directories, and reloads systemd. Stopping setup alone cannot close the reader's
copy of the event descriptor. Configuration drift must be reconciled rather than
silently removed. The old snapshot service is independent of this package.

## Source validation

`python3 packaging/broker/test_manage.py` exercises install/remove, existing
configuration preservation, payload drift, installed drift and symlink-parent
refusal entirely under owned directories. `--destdir` supports unprivileged
package staging without systemd calls. Unit verification uses a shadow copy with
the executable replaced by the staged binary path; real root installation,
credential/capability behavior and kernel event delivery remain unexecuted.
