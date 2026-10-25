# SERVER ADOPTION — Existing Ubuntu / Claude Code handoff

Status: specification · Runtime: NOT_RUN · Date: 2026-10-25.

## 1. First session: read-only admission

Use this procedure before the first server mutation, when initialization is interrupted, or when the session user, checkout or privilege state differs from the handoff. The owner confirmed that the existing Ubuntu 24.04 / Claude Code installation is on the office PC; Q52–Q59 and ADR-032/033 still apply. Actual host compliance has not been observed. Existing installation is the default route; installing Claude does not close HG-F0-00.

1. Locate this supplied folder without moving, deleting or overwriting it. Record its current path locally. From that folder run `python3 12_Acceptance/preflight_server.py`; optionally redirect its selected, nonsecret JSON facts to a local evidence file. The probe makes no changes and no external calls; on a non-Ubuntu host or insufficient permissions it reports mismatches/unknowns. It does not read SSH, sudo or Claude authentication files. A local laptop result is a tooling check, never AMT server acceptance.
2. Read the JSON and complete the human checks below. Ask the owner **one decision at a time**, with the next blocking question first. Put completed observations and unresolved items in `build/F0/ADOPTION.md`; until canonical directories exist, keep that record beside this supplied folder and transfer it after reconciliation. Keep secrets, IP inventories, public/private keys, account tokens and raw command output out of shared evidence.
3. Reconcile every mismatch to the existing owner decisions. Preserve data, workloads, access, Claude login and local changes. An unreadable fact is `unknown`, not `pass`. A fresh install, formatting, disk/RAID changes, changing SSH/firewall, credential copying or reviving builder sudo is never inferred from a failed preflight. Prepare an exact change/rollback plan and the relevant HUMAN_GATE before the owner executes the blocked step.

Admission record (one row per item, with `match | mismatch | unknown`, evidence timestamp, actor, proposed action and required gate):

| Area | Required observation / handback |
|---|---|
| Host / data | Ubuntu Server 24.04, office PC `amt-pc`; owner identifies existing workloads/data and a usable restore point before changes. A different host requires an explicit superseding decision; this route does not change Q52. |
| Disks / power | mdadm RAID1 `/dev/md0`, both members healthy, both ESP boot paths, UPS/BIOS and physical protection. Console-only/disk tests stay owner actions (HG-F0-01, F0-AT-12/19/22). Presence of RAID alone proves no boot or recovery test. |
| Network | Static IPv4, Omada VLAN/ACL, DNS, IPv6 policy and no public ingress (HG-F0-07/08); Tailscale policy/device approval and only owner devices (HG-F0-04). An existing public SSH session needs a separately reviewed migration with local-console recovery and a second verified Tailscale session before it is closed. |
| Accounts / authority | `owner`, `builder`, `amt-build`, groups and home permissions. Owner inspects effective sudo policy locally and records `initial_broad | narrowed | revoked | unknown` without copying policy/auth files. Existing narrowed/revoked authority is preserved; root work is performed by owner or separately scoped HG-OPS-02. |
| Claude / versions | In the intended `builder` session, check installed version against the exact reviewed pin and confirm the intended subscription/login interactively. Existing login under another account is recorded; the owner logs in as `builder` when required. Authentication files are never copied, printed or reset. |
| Repository / gates | Owner confirms GitHub origin, rulesets, signer/deploy keys and the local checkout/dirty-work inventory without printing key material (HG-F0-05); age custody is HG-F0-03. Record each prerequisite gate as open/closed with human evidence. Existing files/commits are preserved. |

Completion: the admission record names the route, every mismatch has a reviewed action/owner gate, and every prerequisite for the next mutation is closed with evidence. Open gates block only dependent work; safe planning and local document validation may continue.

## 2. Adopt the existing office PC (default)

1. Keep the installed OS, current data, login and checkout intact. The initializer in §4 **refuses** an already initialized/Claude/SSH/Tailscale host; adoption never calls it.
2. For each missing F0 prerequisite, prepare only that change and its reversal, identify the owner gate, then verify its result. Implement version changes through a reviewed plan; retain an existing approved version and login. Reconcile unauthorized or unexpected privileges as a blocker rather than expanding them.
3. Close HG-F0-00 only when the equivalent user/access/repo/Claude prerequisites have human evidence. Completed F0 tasks are reused only if their acceptance evidence matches the current host/config; continue at the first unverified task. The whole F0 phase remains `NOT_RUN`/blocked until its actual acceptance tests run; admission does not claim production readiness.

## 3. Session and directory handoff

The canonical monorepo layout is `repo_root=/srv/builder/wolter-amt`, `project_os_root=$repo_root/project-os`. The supplied Project OS folder becomes that `project-os` child through the owner-reviewed HG-F0-05 repo preparation. Reuse a matching existing checkout and preserve its local work. A different local path is documented during admission; reconcile it before relying on canonical commands.

From the owner's existing SSH session use `sudo -iu builder` (the disabled-password builder is not entered with `su - builder`). As `builder`, run each command in order:

```bash
repo_root=/srv/builder/wolter-amt
project_os_root="$repo_root/project-os"
test "$(id -un)" = builder || exit 1
test -f "$project_os_root/CLAUDE.md" || exit 1
cd "$project_os_root"
python3 12_Acceptance/validate_bundle.py --context-pack F0 --out build/F0/CONTEXT_PACK.md
claude
```

`build/` paths in the Project OS, phase packs, gate records and handoff commands are relative to `project_os_root` unless a command explicitly states another directory. Application source, `infra/`, `config/`, `secrets/`, package-manager operations and branch operations belong to `repo_root`; state the directory explicitly when switching. Build/test commands retain the unprivileged clean-export rule from F0 task 2. Starting Claude from `project_os_root` loads its `CLAUDE.md`; confirm the existing builder login interactively, then instruct: “Read CLAUDE.md; complete SERVER_ADOPTION admission; continue the first unverified F0 task. Ask my blocking decisions one at a time.”

## 4. Fresh initialization and safe continuation (owner only)

Use this branch only after the owner explicitly chooses a fresh OS installation under HG-F0-00, with data preservation/restore disposition and physical actions approved. The current existing-office-PC handoff uses §2. A replacement host after production loss uses the separate locked recovery procedure in BACKUP_RESTORE §5 and `--rebuild`, never build mode.

The following is a **reference initializer to implement and review**, not evidence that a script ran. Export its code block to `infra/bootstrap/00-owner-bootstrap.sh` only after the owner has reviewed its version pins, checksums and exact host plan. The precondition checks run before all mutations. Initialization is run once; completed state refuses all replay. `--resume` accepts only the same reviewed script, mode and public inputs, skips completed checkpoints and stops on any in-flight step or missing privilege checkpoint. It never rewrites a completed privilege step. A narrower/missing builder policy is preserved rather than restored to broad sudo.

Partial initialization: owner inspects `/var/lib/amt-bootstrap` locally (root-owned 0700). If there is no `.inflight` file **and `03-privileges.done` exists**, `--resume` continues from the next checkpoint. If initialization stopped before the privilege checkpoint (including after `02-identities.done` but before `03-privileges.inflight`), resume stops before all mutations. The owner separately completes/verifies any missing package/identity prerequisite, then reviews the required privilege action and preserves an existing narrowed/revoked state or makes an explicitly authorized scoped grant, verifies it locally, and records `03-privileges.done`; resume itself never creates a grant. If a step is in flight, the owner verifies each postcondition in the table, finishes only the missing commands with the same approved pins and existing authority, and only then renames that single `<step>.inflight` to `<step>.done`. Do not delete the state or rerun a whole interrupted stage to get past a failure. If the stored script/input digest is missing or differs, stop and reconcile under the adoption record. Resume never silently edits the digest to accept another script.

| Checkpoint | Required reconciliation before marking done |
|---|---|
| `01-packages` | OS/timezone and package operation finished; no pending package-manager transaction. |
| `02-identities` | Accounts/home modes match F0 task 2; existing `authorized_keys` lines retained, intended key present once; unprivileged `amt-build` isolation verified. |
| `03-privileges` | `visudo -c` passes; actual privilege stage recorded. Preserve a narrowed/revoked builder policy, even if the step stopped before its done marker. Missing initial grant requires a new explicit owner action; resume never grants it again. |
| `04-tailscale` | Approved pinned package, owner-approved node and exact task-2 flags verified; consumed auth key removed from tmpfs. A successful enrollment is retained, never auto-reauthenticated by resume. |
| `05-access` | Hardening and socket/udev binding match task 4, Tailscale SSH test passed with console recovery available, no non-Tailscale SSH listener. |
| `06-claude` | Reviewed Node/Claude pins confirmed; existing installation and authentication retained. No reinstall or auth reset to force a green checkpoint. |
| `07-checkout` | Distinct per-repo deploy keys registered through HG-F0-05, SSH aliases/verified known_hosts preserved, expected origin/worktree present with local work intact, directory permissions and build workspace correct. |

Once every checkpoint is complete, `complete` prevents further initializer use. F1 narrowing and F6 revocation are later authority transitions; a completed or abandoned initializer never reverses them. A production/release marker also blocks the initializer. Post-bootstrap F0 scripts must implement their own tested idempotency contract; that contract does not make this fresh-host initializer replayable.

```bash
#!/usr/bin/env bash
# 00-owner-bootstrap.sh — fresh-host initialization only; run as root at the local console (HG-F0-00).
# Existing installations use SERVER_ADOPTION.md, never this initializer. Completed initialization is not replayable.
# Usage: 00-owner-bootstrap.sh              first build on the AMT PC (also a host lost before F2 live intake: no production data yet)
#        00-owner-bootstrap.sh --rebuild    new PC after host loss from F2 on: never creates builder sudo (P-05); the owner then runs the
#                                           reviewed infra/bootstrap/*.sh from the signed release-* tag (BACKUP_RESTORE §5.1)
#        00-owner-bootstrap.sh --resume     continue after completed checkpoints of an interrupted fresh initialization
# An in-flight checkpoint requires owner reconciliation before --resume; it is never replayed automatically.
set -euo pipefail
die() { echo "ERROR: $*" >&2; exit 1; }
REQUEST="${1:-build}"
[[ "$#" -le 1 ]] || die "usage: $0 [--rebuild|--resume]"
[[ "$REQUEST" == "build" || "$REQUEST" == "--rebuild" || "$REQUEST" == "--resume" ]] || die "usage: $0 [--rebuild|--resume]"
[[ "$EUID" == 0 ]] || die "run as root at the local console"
STATE=/var/lib/amt-bootstrap
[[ ! -L "$STATE" ]] || die "bootstrap state must not be a symlink"
SCRIPT_SHA="$(sha256sum -- "$0" | cut -d' ' -f1)"
if [[ "$REQUEST" == "--resume" ]]; then
  [[ -d "$STATE" && ! -e "$STATE/complete" ]] || die "no incomplete init; use adoption/recovery, never replay initialization"
  [[ "$(stat -c '%u:%a' "$STATE")" == 0:700 ]] || die "bootstrap state must be root-owned 0700"
  [[ "$(cat "$STATE/script.sha256")" == "$SCRIPT_SHA" ]] || die "resume requires the exact reviewed script"
  MODE="$(cat "$STATE/mode")"
  [[ "$MODE" == build || "$MODE" == --rebuild ]] || die "invalid saved mode"
  if compgen -G "$STATE/*.inflight" >/dev/null; then die "interrupted step: owner must reconcile it per SERVER_ADOPTION, not replay it"; fi
  [[ -e "$STATE/03-privileges.done" ]] || die "resume cannot grant privileges: owner must reconcile and complete 03-privileges explicitly"
else
  [[ ! -e "$STATE" ]] || die "initialization already started; use --resume or adoption"
  # All these guards run before any mutation, including package installs and sudo/key changes.
  ! id builder >/dev/null 2>&1 || die "builder already exists; use adopt_existing"
  ! id amt-build >/dev/null 2>&1 || die "amt-build already exists; use adopt_existing"
  [[ ! -e /srv/builder && ! -e /opt/wolter-amt && ! -e /etc/sudoers.d/90-builder ]] || die "existing AMT state; use adopt_existing"
  ! command -v claude >/dev/null 2>&1 || die "Claude already installed; use adopt_existing"
  ! command -v tailscale >/dev/null 2>&1 || die "Tailscale already installed; use adopt_existing"
  ! dpkg -s openssh-server >/dev/null 2>&1 || die "existing SSH installation; use adopt_existing"
  MODE="$REQUEST"
fi
[[ ! -e /opt/wolter-amt/current ]] || die "release exists; use operational recovery, not bootstrap"
# No secrets are recorded in state. Inputs/pins are checked again on every continuation.
OWNER_PUBKEY="${OWNER_PUBKEY:?export OWNER_PUBKEY='ssh-ed25519 AAAA... owner@laptop'}"
REPO_SSH_URL="${REPO_SSH_URL:?export REPO_SSH_URL='git@github-amt:<org>/wolter-amt.git'}"
NODE_SETUP_SHA256="${NODE_SETUP_SHA256:?verified NodeSource setup checksum required}"
CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION:?exact approved pinned version required}"
GITHUB_HOSTKEYS_FILE="${GITHUB_HOSTKEYS_FILE:?owner verified GitHub known_hosts file required}"
TAILSCALE_VERSION="${TAILSCALE_VERSION:?exact approved pinned Tailscale version required}"
TAILSCALE_KEYRING_SHA256="${TAILSCALE_KEYRING_SHA256:?verified Tailscale apt keyring checksum required}"
[[ "$OWNER_PUBKEY" != *$'\n'* && "$OWNER_PUBKEY" != *$'\r'* ]] || die "public key must be one line"
[[ "$OWNER_PUBKEY" =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ .*)?$ ]] || die "OWNER_PUBKEY must be one ssh-ed25519 public key"
[[ "$REPO_SSH_URL" =~ ^git@github-amt:[A-Za-z0-9_.-]+/wolter-amt\.git$ ]] || die "REPO_SSH_URL must use the github-amt alias"
[[ "$NODE_SETUP_SHA256" =~ ^[a-fA-F0-9]{64}$ ]] || die "NODE_SETUP_SHA256 is not a sha256"
[[ "$CLAUDE_CODE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "CLAUDE_CODE_VERSION must be an exact x.y.z"
[[ "$TAILSCALE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "TAILSCALE_VERSION must be an exact x.y.z"
[[ "$TAILSCALE_KEYRING_SHA256" =~ ^[a-fA-F0-9]{64}$ ]] || die "TAILSCALE_KEYRING_SHA256 is not a sha256"
test -s "$GITHUB_HOSTKEYS_FILE" || die "the GitHub known_hosts file is missing or empty"
[[ "$(hostname)" == "amt-pc" ]] || die "hostname must be amt-pc (set it in the installer)"
grep -q '^md0 : active raid1' /proc/mdstat || die "RAID1 /dev/md0 from the installer is missing (F0-AT-12)"
ip -4 route show default | grep -q . || die "no default route: set the static IPv4 from HG-F0-07 in the installer"
INPUT_SHA="$(printf '%s\0' "$OWNER_PUBKEY" "$REPO_SSH_URL" "$NODE_SETUP_SHA256" "$CLAUDE_CODE_VERSION" "$TAILSCALE_VERSION" "$TAILSCALE_KEYRING_SHA256" "$(sha256sum -- "$GITHUB_HOSTKEYS_FILE" | cut -d' ' -f1)" | sha256sum | cut -d' ' -f1)"
if [[ "$REQUEST" == --resume ]]; then
  [[ "$(cat "$STATE/inputs.sha256")" == "$INPUT_SHA" ]] || die "resume inputs changed; owner reconciliation required"
else
  install -d -m 700 -o root -g root "$STATE"
  printf '%s\n' "$MODE" > "$STATE/mode"
  printf '%s\n' "$SCRIPT_SHA" > "$STATE/script.sha256"
  printf '%s\n' "$INPUT_SHA" > "$STATE/inputs.sha256"
fi
run_step() {
  local step="$1"; shift
  [[ ! -e "$STATE/$step.inflight" ]] || die "owner reconciliation required: $step"
  if [[ -e "$STATE/$step.done" ]]; then return 0; fi
  # Leave inflight on error/power loss. --resume stops before all mutations until the owner reconciles it.
  ( set -o noclobber; printf '%s\n' "$step" > "$STATE/$step.inflight" )
  "$@"
  mv "$STATE/$step.inflight" "$STATE/$step.done"
}
ensure_exact() {
  local file="$1" mode="$2" tmp
  [[ ! -L "$file" ]] || die "refuse symlink: $file"
  tmp="$(mktemp /run/amt-init.XXXXXX)"
  cat > "$tmp"
  if [[ -e "$file" ]]; then
    cmp -s "$tmp" "$file" || { rm -f "$tmp"; die "existing managed file differs; preserve and reconcile: $file"; }
    rm -f "$tmp"
  else
    install -m "$mode" -o root -g root "$tmp" "$file"
    rm -f "$tmp"
  fi
}
step_packages() {

timedatectl set-timezone UTC
apt-get update
apt-get -y full-upgrade
apt-get -y install git curl ca-certificates sudo ufw

}
step_identities() {
# owner already exists from the installer: its password is for the local console only; SSH stays key-only (Q58)
for u in owner builder; do
  id "$u" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$u"
  install -d -m 700 -o "$u" -g "$u" "/home/$u/.ssh"
  [[ ! -L "/home/$u/.ssh/authorized_keys" ]] || die "authorized_keys is a symlink"
  touch "/home/$u/.ssh/authorized_keys"
  if ! grep -qxF -- "$OWNER_PUBKEY" "/home/$u/.ssh/authorized_keys"; then
    printf '\n%s\n' "$OWNER_PUBKEY" >> "/home/$u/.ssh/authorized_keys"
  fi
  chown "$u:$u" "/home/$u/.ssh/authorized_keys"
  chmod 600 "/home/$u/.ssh/authorized_keys"
done
# Unprivileged build/test user (P-05): no login shell, no sudo, no docker, no secrets, no access to the builder checkout
id amt-build >/dev/null 2>&1 || adduser --system --group --home /srv/amt-build --shell /usr/sbin/nologin amt-build
}
step_privileges() {
[[ "$REQUEST" != --resume ]] || die "resume never grants privileges; owner reconciliation required"
usermod -aG sudo owner
printf '%s\n' 'owner ALL=(ALL) NOPASSWD:ALL' | ensure_exact /etc/sudoers.d/80-owner 440
if [[ "$MODE" == "build" ]]; then
  # Temporary (P-05): narrowed to a command allowlist when F1 is accepted (F1-AT-26); removed before F6 Step 1 (HG-F6-06, F6-AT-11)
  [[ ! -e /etc/sudoers.d/90-builder ]] || die 'existing builder policy is preserved; reconcile privileges'
  printf '%s\n' 'builder ALL=(ALL) NOPASSWD:ALL' | ensure_exact /etc/sudoers.d/90-builder 440
else
  [[ ! -e /etc/sudoers.d/90-builder ]] || die "rebuild must not contain builder sudo; preserve and reconcile it"
fi
visudo -c || die "sudoers check failed"

}
step_tailscale() {
# Tailscale (Q58, HG-F0-04), pinned. The owner already applied 09_Config_Templates/tailscale-policy.hujson.
# SSH reaches this PC only over tailscale0 (F0 task 4 binds ssh.socket to tailscale0); no Tailscale SSH, MagicDNS, routes or exit node.
# Every later `tailscale up` (re-auth, BACKUP_RESTORE §7) repeats exactly these flags plus --force-reauth: flags are not persisted.
ts_keyring=/usr/share/keyrings/tailscale-archive-keyring.gpg
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o "$ts_keyring"
printf '%s  %s\n' "$TAILSCALE_KEYRING_SHA256" "$ts_keyring" | sha256sum -c - || die "Tailscale keyring checksum mismatch"
echo "deb [signed-by=$ts_keyring] https://pkgs.tailscale.com/stable/ubuntu noble main" > /etc/apt/sources.list.d/tailscale.list
apt-get update
apt-get -y install "tailscale=$TAILSCALE_VERSION"
apt-mark hold tailscale
ts_key_file=/run/amt-ts-authkey        # tmpfs; the auth key never appears on a command line
( umask 077; read -r -s -p "One-time, pre-approved tag:amt auth key (HG-F0-04): " k; echo; printf '%s' "$k" > "$ts_key_file" )
tailscale up --auth-key="file:$ts_key_file" --advertise-tags=tag:amt --ssh=false --accept-dns=false --accept-routes=false
rm -f "$ts_key_file"
echo "== AMT tailnet IPv4: $(tailscale ip -4). Disable key expiry for this node in the Tailscale admin console (HG-F0-04)."

}
step_access() {
# sshd only on tailscale0 from its very first start (Q58, F0 task 4). OpenSSH is installed here, not by the installer:
# the hardening file, the socket drop-in and the udev rule exist before the package starts the socket.
# The socket is bound to the device and started by the device, never from sockets.target (boot would wait 90 s for
# tailscale0); sshd never runs standalone (it would bind *:22).
if dpkg -s openssh-server >/dev/null 2>&1; then die "existing OpenSSH state; owner reconciliation required"; fi
install -d /etc/ssh/sshd_config.d /etc/systemd/system/ssh.socket.d /etc/systemd/system/ssh.service.d
printf 'PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nAllowUsers owner builder\nMaxAuthTries 3\n' > /etc/ssh/sshd_config.d/10-amt.conf
printf '[Socket]\nBindToDevice=tailscale0\n' > /etc/systemd/system/ssh.socket.d/10-tailscale0.conf
printf '[Unit]\nRequires=ssh.socket\nAfter=ssh.socket\n' > /etc/systemd/system/ssh.service.d/10-socket-only.conf
printf '%s\n' 'SUBSYSTEM=="net", KERNEL=="tailscale0", TAG+="systemd", ENV{SYSTEMD_WANTS}+="ssh.socket"' > /etc/udev/rules.d/90-amt-tailscale0.rules
udevadm control --reload-rules
systemctl daemon-reload
apt-get -y install openssh-server
systemctl disable ssh.socket
systemctl disable ssh.service
systemctl restart ssh.socket
install -d -m 0755 /run/sshd   # privilege separation dir; ssh.service creates it only when the first connection starts it
sshd -t || die "sshd configuration test failed"
ss -ltnH 'sport = :22' | grep -q '%tailscale0' || die "sshd is not listening on tailscale0"
if ss -ltnH 'sport = :22' | grep -qv '%tailscale0'; then die "sshd listens outside tailscale0"; fi
ufw default deny incoming
ufw default allow outgoing
ufw allow in on tailscale0 to any port 22 proto tcp
ufw --force enable

}
step_claude() {
# Node 24 (NodeSource) + Claude Code for builder
# This step installs only; it never copies, clears or reads Claude authentication state.
if command -v claude >/dev/null 2>&1; then die "existing Claude install is preserved; owner verifies pin and marks checkpoint"; fi
node_setup_file="$(mktemp /tmp/amt-node-setup.XXXXXX)"
curl -fsSL https://deb.nodesource.com/setup_24.x -o "$node_setup_file"
printf '%s  %s\n' "$NODE_SETUP_SHA256" "$node_setup_file" | sha256sum -c - || die "NodeSource setup checksum mismatch"
bash "$node_setup_file"
rm -f "$node_setup_file"
apt-get -y install nodejs
npm install -g "@anthropic-ai/claude-code@$CLAUDE_CODE_VERSION"   # exact reviewed release; verify official method before bootstrap

}
step_checkout() {
# Deploy keys for builder — GitHub does NOT allow reusing one deploy key on two repos, so one key per repo.
# HG-F0-05 created the repos, rulesets and signer key; the owner adds these keys now, at this prompt.
# Branch pushes only: the tag ruleset must refuse release-* and F*-done for this key (verified by F0-AT-15).
for r in amt landing; do
  sudo -H -u builder bash -c "test -f ~/.ssh/id_ed25519_$r || ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519_$r -C builder-$r@amt-pc"
  echo "== Add this deploy key to wolter-$r (write = branch pushes; never a ruleset bypass actor):"
  cat "/home/builder/.ssh/id_ed25519_$r.pub"
done
[[ ! -e /home/builder/.ssh/config ]] || die 'existing SSH client config is preserved; reconcile aliases'
sudo -H -u builder bash -c 'cat > ~/.ssh/config <<CFG
Host github-amt
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_amt
  IdentitiesOnly yes
Host github-landing
  HostName github.com
  IdentityFile ~/.ssh/id_ed25519_landing
  IdentitiesOnly yes
CFG
chmod 600 ~/.ssh/config'
read -r -p "Both deploy keys added on GitHub (and, on --rebuild, the old ones removed)? [y/N] " ok
[[ "$ok" == "y" ]] || die "add the deploy keys first"
install -d -m 700 -o builder -g builder /srv/builder              # amt-build can neither traverse nor read the builder checkout
install -d -m 750 -o amt-build -g amt-build /srv/amt-build/work   # builds run on clean exports here (F0 task 2), never in the checkout
printf 'd /srv/amt-build/work 0750 amt-build amt-build 7d\n' > /etc/tmpfiles.d/amt-build.conf   # run directories older than 7 days are removed by systemd-tmpfiles-clean.timer
[[ ! -L /home/builder/.ssh/known_hosts ]] || die "known_hosts is a symlink"
touch /home/builder/.ssh/known_hosts
while IFS= read -r hostline || [[ -n "$hostline" ]]; do
  if ! grep -qxF -- "$hostline" /home/builder/.ssh/known_hosts; then printf '\n%s\n' "$hostline" >> /home/builder/.ssh/known_hosts; fi
done < "$GITHUB_HOSTKEYS_FILE"
chown builder:builder /home/builder/.ssh/known_hosts
chmod 600 /home/builder/.ssh/known_hosts
# REPO_SSH_URL must use the alias, e.g. git@github-amt:<owner>/wolter-amt.git (landing: git@github-landing:<owner>/wolter-landing.git)
if [[ -e /srv/builder/wolter-amt ]]; then
  sudo -H -u builder git -C /srv/builder/wolter-amt rev-parse --is-inside-work-tree >/dev/null || die "existing checkout is invalid; preserve it"
  [[ "$(sudo -H -u builder git -C /srv/builder/wolter-amt remote get-url origin)" == "$REPO_SSH_URL" ]] || die "checkout origin mismatch; preserve it"
  # Existing commit and local work are preserved. A pull/reset/clean is never part of resume.
else
  sudo -H -u builder git clone "$REPO_SSH_URL" /srv/builder/wolter-amt
fi
}
run_step 01-packages step_packages
run_step 02-identities step_identities
run_step 03-privileges step_privileges
run_step 04-tailscale step_tailscale
run_step 05-access step_access
run_step 06-claude step_claude
run_step 07-checkout step_checkout
printf '%s\n' complete > "$STATE/complete"
if [[ "$MODE" == "build" ]]; then
  echo "== Next: ssh owner@<tailnet IP> (or stay at the console); sudo -iu builder; cd /srv/builder/wolter-amt/project-os; claude   (confirm the existing Max 20x login), then tell it: 'Read CLAUDE.md, complete SERVER_ADOPTION first, then start only verified F0 tasks.'"
else
  echo "== Rebuilt PC ready. Builder has no sudo. Run the reviewed infra/bootstrap/*.sh as root from the signed release-* tag (BACKUP_RESTORE §5.1); scoped builder help only via HG-OPS-02."
fi
```

## 5. F0 implementation references

Read the named subsection before implementing its matching F0 task or investigating a failed acceptance test. These are the unchanged detailed requirements disclosed from F0; the phase file retains task order, gates and the full acceptance table. Numbered task cross-references retain their F0 task numbers.

### 5.1 SSH and host hardening

4. **SSH va host hardening**
   - `/etc/ssh/sshd_config.d/10-amt.conf` (bootstrap yozadi, builder tekshiradi): `PermitRootLogin no` · `PasswordAuthentication no` · `KbdInteractiveAuthentication no` · `AllowUsers owner builder` · `MaxAuthTries 3`.
   - **sshd faqat `tailscale0` interfeysida** (Q58, tasdiqlangan xulosa): `ListenAddress` qo‘yilmaydi (manzil boot’da kech paydo bo‘lsa yoki tugun qayta autentifikatsiyada yangi IP olsa SSH yo‘qolardi). Buning o‘rniga `/etc/systemd/system/ssh.socket.d/10-tailscale0.conf` → `[Socket]` `BindToDevice=tailscale0`: socket faqat `tailscale0` da tinglaydi — joriy noble paketidagi `ssh.socket` IPv4 va IPv6 uchun alohida `ListenStream` ochadi (`BindIPv6Only=ipv6-only`), shuning uchun `ss` ikki listener ko‘rsatadi: `0.0.0.0%tailscale0:22` va `[::]%tailscale0:22`; boshqa interfeysdan kelgan paket sshd’ga yetmaydi. systemd socket’ga shu qurilmaga `BindsTo=`/`After=` qo‘shadi (qurilma yo‘qolsa socket to‘xtaydi), `tailscale0` esa faqat `tailscaled` ishga tushgandan keyin paydo bo‘ladi — shuning uchun socket **`sockets.target` dan ishga tushirilmaydi** (`systemctl disable ssh.socket`; aks holda har boot qurilmani 90 s kutib turib qoladi), uni faqat qurilmaning o‘zi ishga tushiradi: udev qoidasi `/etc/udev/rules.d/90-amt-tailscale0.rules` → `SUBSYSTEM=="net", KERNEL=="tailscale0", TAG+="systemd", ENV{SYSTEMD_WANTS}+="ssh.socket"` (`tailscale0` har paydo bo‘lganda — boot va `tailscaled` restart’dan keyin; qayta autentifikatsiya qurilmani qayta yaratmaydi). sshd hech qachon mustaqil ishlamaydi: `/etc/systemd/system/ssh.service.d/10-socket-only.conf` → `[Unit]` `Requires=ssh.socket`, `After=ssh.socket`, va `systemctl disable ssh.service` (mustaqil sshd `*:22` ga bog‘lanardi). Bu sozlamalarni va `10-amt.conf` ni owner bootstrap’ning o‘zida, `tailscale up` dan keyin va `openssh-server` o‘rnatilishidan **oldin** qo‘yadi (Appendix A; installer OpenSSH o‘rnatmaydi) — sshd birinchi ishga tushishidanoq faqat `tailscale0` da. LAN NIC’da ufw ikkinchi qatlam (5-vazifa); `tailscale0` yo‘q paytda kirish — owner lokal konsoli. F0-AT-21.
   - Tailscale SSH ishlatilmaydi (`--ssh=false`): kirish oddiy sshd va kalit bilan.
   - **Xotiradagi PII diskka tushmaydi (Q62):** installer yaratgan `/swap.img` o‘chiriladi (`swapoff -a`, `/etc/fstab` qatori olib tashlanadi; kerak bo‘lsa faqat zram); `/etc/sysctl.d/60-amt-nocore.conf` → `kernel.core_pattern=|/bin/false`, `fs.suid_dumpable=0`; `/etc/systemd/system.conf.d/` da `DefaultLimitCORE=0`; systemd-coredump `Storage=none`; apport o‘chiriladi; `sleep`, `suspend`, `hibernate` va `hybrid-sleep` target’lari mask qilinadi; Node servislarida heap snapshot flag’lari yo‘q (F0-AT-20).

### 5.2 Network and firewall

5. **Tarmoq va firewall** ([ADR-033](../04_ADR/ADR-033-tunnel-tailscale-omada-access.md))
   - **Omada (HG-F0-07, owner; Q59):** ER605 v2.0 va SG2428P v5.30, apparat controller OC200/OC300.
     - AMT o‘z VLAN’ida; PC’ga **statik IPv4** (gateway boshqaruv ACL’i DHCP unicast yangilanishini ham to‘sadi); PC’ning SG2428P porti shu VLAN’ning untagged access porti, yoki PC ER605 portiga to‘g‘ridan ulanadi (Q53 izohi).
     - ER605: AMT tarmog‘i uchun **"Gateway Management Page"** ACL — gateway’ning barcha interfeys IP’lariga (AMT VLAN gateway manzili ham) AMT’dan paket rad; routing va default route ishlayveradi. Switch va controller ACL: AMT → SG2428P va controller boshqaruv IP’lari rad.
     - AMT ↔ ofis LAN ikki tomonga rad; AMT → internet ruxsat; AMT uchun port forward, virtual server, DMZ yoki UPnP yo‘q; AMT VLAN’da IPv6 o‘chiq. Controller hech qachon AMT PC’da ishlamaydi.
   - **ufw (server):** `/etc/default/ufw` da `IPV6=yes`; `ufw default deny incoming; ufw default allow outgoing` — LAN NIC’da hech qanday kiruvchi port, shu jumladan 22, ochilmaydi (Q57). `ufw allow in on tailscale0 to any port 22 proto tcp` niyatni yozib qo‘yadi, lekin `--netfilter-mode=on` da `tailscaled` `tailscale0` dagi trafikni va o‘z UDP portini o‘zi qabul qiladi: tailnet’dagi haqiqiy filtr — Tailscale siyosati (faqat owner → `tag:amt:22`), lokal servislar esa baribir faqat `127.0.0.1` da (F0-AT-03).
   - **nftables:** AMT’ning per-UID egress qoidalari (F1) faqat o‘z `table inet amt_egress` jadvalida, uni `amt-egress.service` (oneshot) yuklaydi; fayl `flush ruleset` ishlatmaydi va Ubuntu’ning standart `nftables.service` o‘chiq qoladi — ufw, Docker va tailscaled jadvallari reboot’dan keyin ham saqlanadi (F0-AT-21). `cloudflared` UID loopback’da faqat `127.0.0.1:8080` (Caddy) va systemd-resolved stub’i `127.0.0.53:53`/`127.0.0.54:53` (DNS, udp+tcp) ga, tashqariga faqat Cloudflare Tunnel edge’ining 7844 portiga (tcp+udp) chiqadi. Root servislar (`amt-backup`, `amt-release`, managed runner) UID bo‘yicha ajratilmagani uchun ularning egress’i systemd `IPAddressDeny=any` + `IPAddressAllow=` bilan cheklanadi (`runtime-isolation.yaml#services`); istisno — `tailscaled` (ixtiyoriy peer’larga UDP). Docker konteynerlari trafigi per-UID qoidalarga ko‘rinmaydi — ular `DOCKER-USER` zanjirida qat’iy nomli bridge’lar (`br-amt-langfuse`, `br-amt-telegram`) bo‘yicha va faqat bridge’dan chiqib ketayotgan yangi ulanishlar uchun filtrlanadi (Docker Engine ≥ 29.0 da `firewall-backend: iptables` pin qilinadi) ([F1_Platform](F1_Platform.md) 5-vazifa).
   - **Tailscale siyosati (HG-F0-04):** [tailscale-policy.hujson](../09_Config_Templates/tailscale-policy.hujson) — `tagOwners` (faqat owner `tag:amt` ni qo‘llaydi), yagona qoida owner → `tag:amt:22`, `tag:amt` manba bo‘lgan qoida yo‘q, `tests` bloki har saqlashda ishlaydi va xato siyosatni rad etadi. Owner uni auth key yaratishdan oldin admin konsolga qo‘yadi va tailnet’da device approval’ni yoqadi; builder F0’da shu matnni `infra/tailscale/acl.hujson` ga commit qiladi. O‘zgarish faqat PR va HG-F0-04 bilan (F0-AT-08).
   - **DNS:** statik netplan’da `1.1.1.1` va `9.9.9.9` (systemd-resolved, stub `127.0.0.53`/`127.0.0.54`); `resolved.conf.d` da `LLMNR=no`, `MulticastDNS=no` (5355/5353 tinglanmaydi); gateway faqat default route; Tailscale DNS qabul qilinmaydi (`--accept-dns=false`).

### 5.3 Automatic security updates

6. **Avtomatik xavfsizlik yangilanishlari** — `unattended-upgrades` (faqat security); `apt-daily-upgrade.timer` drop-in’ida avval `OnCalendar=` (bo‘sh — standart 06:00 ni o‘chiradi), keyin `OnCalendar=*-*-* 03:30:00 Asia/Tashkent`, `RandomizedDelaySec=0`, `Persistent=false` (o‘tkazib yuborilgan kecha boot’da bajarilmaydi) — 02:00 dagi snapshot’dan keyin va 04:30 dagi `restore_check` muddat tekshiruvidan oldin (`systemctl list-timers` bilan tekshiriladi); o‘sha kechaning snapshot’i tugab tekshirilmagan bo‘lsa `apt-daily-upgrade.service.d/10-amt-snapshot.conf` dagi `ExecCondition=` (u `[Service]` sozlamasi — `.timer` drop-in’ida e’tiborsiz qoladi) yangilanishni o‘tkazib yuboradi; o‘tkazilgan kecha log’ga yoziladi va ketma-ket ikkinchi o‘tkazib yuborish `ALERT_BACKUP_STALE` beradi (snapshot o‘z deadline’i ichida, lekin 03:30 dan keyin tugaydigan bo‘lib qolsa ham yangilanishlar jim to‘xtamaydi); `restore_check` `apt-daily-upgrade.service` faol paytda kutadi (`operations.yaml#local_snapshot.automatic_security_updates`). Avtomatik reboot **yo‘q**, owner rejalashtiradi. `cloudflared` (`--no-autoupdate`) va `tailscale` (apt hold) faqat [UPGRADE](../06_Runbooks/UPGRADE.md) bo‘yicha, oldidan `amt-backup --pre-upgrade` bilan yangilanadi.

### 5.4 Cloudflare Tunnel and Caddy

9. **Cloudflare Tunnel va Caddy** (HG-F0-02; Q57)
   - `cloudflared` (rasmiy repo, pinned) — `cloudflared.service`, UID `cloudflared`, buyruq `cloudflared --no-autoupdate --metrics 127.0.0.1:20241 tunnel run`. Tunnel tokeni sops’da; servisga faqat `EnvironmentFile=/run/amt/secrets/cloudflared.env` dagi `TUNNEL_TOKEN` sifatida beriladi (`0600`, faqat `cloudflared` o‘qiydi) — buyruq qatorida hech qachon emas. Listener faqat loopback’dagi metrics; chiquvchi ulanish — Cloudflare Tunnel edge (7844).
   - Tunnel **masofadan boshqariladi** (Zero Trust dashboard, HG-F0-02): public hostname’lar `mar.wolter.uz`, `mar2.wolter.uz`, `mar3.wolter.uz` → `http://127.0.0.1:8080`, oxirida catch-all `http_status:404`; boshqa hostname yo‘q. Kutilgan holat git’da — `infra/cloudflared/ingress.expected.yaml`; lokal `config.yml` ingress’i ishlatilmaydi. Tenglik Cloudflare API read-back bilan tekshiriladi (F0-AT-04).
   - HG-F0-02 da owner Cloudflare akkauntini ham qattiqlashtiradi: 2FA, a’zolar ro‘yxatida faqat owner, keraksiz API token yo‘q. Token’ni aylantirish va ulanishlarni uzish uchun "Cloudflare Tunnel Write" huquqli API token owner’da qoladi, AMT PC’ga qo‘yilmaydi ([BACKUP_RESTORE §7](../06_Runbooks/BACKUP_RESTORE.md)).
   - Caddy 2 (rasmiy repo) faqat `127.0.0.1:8080` da tinglaydi: TLS Cloudflare edge’da tugaydi, Caddy’da sertifikat yo‘q. Global `servers { trusted_proxies static 127.0.0.1/32; client_ip_headers Cf-Connecting-Ip }` — mijozning haqiqiy IP’si log va tg-auth’ga (IP o‘zgarishi qoidasi, rate limit, login xabari) shu sarlavhadan o‘tadi; tg-auth forward-auth F1’da ulanadi (Q49), haqiqiy IP F1-AT-06 da tekshiriladi.
   - Hozircha barcha hostlar `respond 503`, servislar F1’da ulanadi.
   - `mar2.wolter.uz` — faqat `/amo/<secret>` va `/meta/<secret>` uchun joy ajratiladi, qolgan yo‘llar `404`. `/tg` yo‘q: ops-bot lokal Bot API’dan foydalanadi ([ARCHITECTURE §5](../03_Architecture/ARCHITECTURE.md)).
   - Tunnel ishlamasa port ochilmaydi va port forward qilinmaydi (Q57); servislar tunnel tiklanguncha tashqaridan yopiq ([INCIDENTS](../06_Runbooks/INCIDENTS.md) INC-11).

### 5.5 UPS, power and RAID monitoring

10. **UPS, elektr va RAID nazorati** (Q53; HG-F0-01)
    - UPS PC, ONT va ER605’ni ta’minlaydi (Q53). AMT VLAN SG2428P orqali o‘tsa switch va Omada controller ham UPS’ga ulanadi (builder aniqlashtirishi) va ishlash vaqti shu PoE yuklamasi bilan o‘lchanadi, yoki PC ER605 portiga to‘g‘ridan ulanadi. BIOS "Restore on AC Power Loss = Power On".
    - UPS’da USB signal porti bo‘lsa — NUT: `upssched` batareyaga o‘tishda (ONBATT) 3600 s taymer boshlaydi va elektr qaytsa (ONLINE) bekor qiladi; taymer tugasa `upsmon -c fsd`; past batareya signali FSD’ni darhol beradi. Faqat upsmon FSD yo‘li POWERDOWNFLAG qo‘yadi va o‘chish oxirida UPS chiqishini o‘chiradi — shundagina elektr qaytganda PC AC yo‘qolganini ko‘radi va BIOS uni yoqadi; skriptdan oddiy `shutdown` buni qilmaydi. `ups.delay.shutdown`, `ups.delay.start` va elektr qaytganda chiqishning yonishi F0-AT-19 da o‘qiladi. UPS buni qo‘llamasa yoki USB port bo‘lmasa — `operations.yaml#host_power.no_killpower_fallback`: PC faqat past batareya signalida o‘chiriladi (UPS bo‘shaydi va qaytgan elektr PC’ni yoqadi), aks holda PC’ni owner qo‘lda yoqadi; holat `build/F0/EVIDENCE.md` da qayd etiladi.
    - `ALERT_HOST_POWER`: UPS batareyada — degraded; past batareya yoki 60 daqiqa → toza o‘chirish boshlandi — critical; qabul qiluvchilar owner va `ops_responder`. F0’da hodisa kodi journal’ga yoziladi, Telegram yetkazilishi F1’da ops-bot bilan ulanadi.
    - RAID: `mdadm --monitor` RAID degradatsiyasida `ALERT_SERVICE_DOWN` beradi (F0-AT-12; Telegram’ga F1’dan).
    - **Uzilish jurnali (Q60):** `amt-outage-log.timer` har kuni journal’dan `cloudflared` ulanishining uzilishi/tiklanishi, `tailscaled`, NUT (ONBATT/ONLINE/FSD) hodisalari va boot vaqtlarini `/var/log/amt/outage.jsonl` ga yozadi (PII yo‘q; `operations.yaml#outage_log`). Zaxira liniya qarori uchun 30 kunlik hisob F0 qabul qilingan kundan boshlanadi; HG-F2-17 dan mustaqil monitor ham manba bo‘ladi.
    - UPS modeli, o‘lchangan ishlash vaqti, disk ro‘yxati va ona plata modeli `build/F0/EVIDENCE.md` ga (HG-F0-01, F0-AT-19).
