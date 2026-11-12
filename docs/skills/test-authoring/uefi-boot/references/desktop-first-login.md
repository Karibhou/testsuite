---
name: desktop-first-login
description: "Proposed firmware boot and desktop first-login qualification contract for issue #1026."
metadata:
  type: reference
  audience: agents
  maturity: draft
---

# Desktop firmware boot and first-login qualification

Status: proposed design for [#1026](https://github.com/projectbluefin/testsuite/issues/1026).
This document supplies a reviewable fixture contract and acceptance cases. It
does not add runtime coverage or approve a suite, privileged fixture, secrets,
or workflow permissions. Hosted evidence and per-image approval are outstanding.

## Scope and existing evidence

The fast desktop smoke lane checks a prepared user session. Its direct-kernel
boot and injected account/autologin cannot establish firmware boot, account
creation, or password authentication. Keep those claims separate in results.

Reuse the [OOBE investigation](../../../../archive/spikes/oobe-first-boot.md)
and [UEFI spike](../../../../archive/spikes/uefi-ovmf-boot.md).
The spike workflow installs systemd-boot and seeds an SSH user. It is a migration
experiment, not proof of the shipped loader or the no-user first-use journey.
The archived GIS mock-mode recommendation covers only wizard UI. Neither is a
passing qualification result for this contract.

Propose one opt-in x86_64 GitHub Actions qualification job, initially on a single
approved Bluefin desktop disk, with OVMF and software rendering. No Secure Boot,
TPM, physical GPU, installer matrix, or server installation claims. Coordinate
firmware fixture ownership with #706; keep native Server installer work in #975.

## Image admission: approve a journey before running

An OCI tag alone is insufficient: how a disk was installed determines whether
a user already exists. Record both immutable image identity and the supported
disk preparation route. Do not infer GIS availability from the desktop name.

| Target | Proposed admission scope | Required journey evidence before admission |
|---|---|---|
| Bluefin desktop, one pinned build | First candidate; not yet admitted | Inspect supported installed disk, GDM configuration, GIS package/vendor policy and initial accounts; record native page sequence or supported credential provisioning route |
| Bluefin LTS and hardware/developer variants | Deferred; no inherited pass from Bluefin | Independent disk and vendor-policy inspection for each admitted build/profile |
| Dakota desktop | Deferred; no substitute for an unreachable Bluefin candidate | Independent loader, display-manager and first-use inspection |
| GNOME OS | Outside initial scope | A different image cannot establish Bluefin first-login coverage |
| No-OOBE desktop profiles | Eligible only with an explicit supported credential route | Identify how users normally create/provision credentials and which native greeter authenticates them |
| Server, headless and KDE profiles | Outside this bounded GNOME design | No desktop result inferred from SSH health or another display manager |

## Admission record and unreachable journeys

The admission record must name the image digest, disk checksum and preparation
recipe/version, loader identity, display manager, initial regular-user inventory
(no shadow/password data), GIS vendor configuration and expected ordered required
screens, locale/keyboard settings, and expected final user/session properties.
For no-OOBE images, name the supported credential provisioning method and state
explicitly that this profile proves login, not UI account creation.

If no supported disk can reach the claimed journey, record `unreachable` with
serial/UI evidence and fail qualification. Do not force GIS with a debug kernel
argument, change vendor page policy, seed a user for a GIS profile, swap images,
or convert the run into a smoke pass. Maintainers approve this admission record
before runtime implementation is treated as image qualification.

### Utah testing candidate, x86_64

Read-only filesystem inspection on 2026-11-12 used
`ghcr.io/projectbluefin/utah@sha256:bb9aea734d6a099444067af29c0783057465f0779ffc058bae4014b4a1cd97e0`
(`utah:testing` at inspection time). This is a candidate record, not an
approved admission or a successful boot.

| Field | Inspection and remaining evidence |
|---|---|
| Disk and preparation | Use the `e2e.yml` `bootc install to-disk` loopback recipe on a fresh 40 GiB disk, ext4 and `--wipe`, without seeding a regular user or enabling GDM autologin. Unlike the smoke recipe, do not substitute systemd-boot or accept a failed bootloader installation for direct-kernel boot. Disk checksum and exact installer/version are **to confirm in #1026's probe child**: no disk was installed or inspected here. |
| Loader | The image contains bootupd 0.3.2, GRUB EFI and systemd-boot packages. `/usr/lib/bootupd/updates/EFI.json` names `grub2-1:2.12-66.fc44,shim-16.1-7` and has a null `default-bootloader`. The actual ESP loader is **to confirm in #1026's probe child** by inspecting the installed disk; package presence alone does not establish what the installer writes. |
| Display manager | GDM 51 is installed. Image `/etc/gdm/custom.conf` contains empty daemon, security and debug sections; no autologin is configured there. `/usr/etc` and `/usr/lib/gdm/{custom,daemon}.conf` are absent, as is `/etc/gdm/daemon.conf`. Installed-disk configuration and the running greeter remain **to confirm in #1026's probe child**. |
| Initial users | `/usr/lib/passwd` is absent. Image `/etc/passwd` has one uid ≥1000: `nobody`, uid/gid 65534, home `/`, shell `/usr/sbin/nologin`; it is not a regular login user. No other such entries were present. Confirm the installed disk has no regular user before boot in #1026's probe child. No shadow data was inspected. |
| Initial setup | GNOME Initial Setup 51.1 is installed. `/usr/share/gnome-initial-setup/vendor.conf` sets `[pages] existing_user_only=language;keyboard`; `/etc/gnome-initial-setup/vendor.conf` sets `[pages] skip=software`. Effective configuration precedence, the ordered page sequence and skipped pages are **to confirm in #1026's probe child**: filesystem inspection alone does not establish the actual first-boot path or conditional pages. |
| Locale and keyboard | Neither `/etc/locale.conf` nor `/etc/vconsole.conf` exists in the image; `/usr/etc` is absent. Effective defaults and any first-boot selection are **to confirm in #1026's probe child**. |
| Final state | Expect a newly created regular user and a usable desktop session. Image `/etc/login.defs` sets `UID_MIN 1000` and `UID_MAX 60000`, but the actual uid and groups, successful authentication and desktop usability are **to confirm in #1026's probe child**; no account was created during inspection. |

The image digest is immutable; repeat inspection and admission if it changes.
Do not infer a disk checksum, page order or successful journey from this record.

## Minimal fixture contract

Proposed interface, not new reusable workflow inputs:

| Boundary | Required information or behavior |
|---|---|
| Input | Admitted immutable image/disk identity, journey profile, expected screens and state checks, bounded timeouts, controlled-failure case identifier |
| Reset | Fresh disposable disk overlay and fresh writable OVMF variable-store copy for every case; immutable base never receives writes |
| Boot | Matching OVMF code/variable templates, QEMU/KVM version and machine recorded; boot the disk's supported loader with no `-kernel`, `-initrd`, `-append` or replacement loader |
| Observation | Host framebuffer checkpoints from the actual guest before a normal user exists; serial collection starts before boot |
| Input | Host-local QEMU monitor keyboard/pointer events to the native GDM/GIS surface; no stand-in UI or post-login session required to start the driver |
| Management | Separately approved diagnostic channel; read guest state and journals without authenticating the tested desktop user or completing setup |
| Output | Case verdict and last reached checkpoint, sanitized provenance, actual UI evidence and serial/journal artifacts on success and failure |
| Teardown | Stop QEMU, detach mounts/loop devices, delete writable disks, variable stores and ephemeral credentials, including on timeout |

## Shared helpers and pre-login input

Use the existing QEMU lifecycle, serial collection and
[framebuffer helper](../../../../../tests/shared/qemu_screendump.py) as starting
points. Its current fixed monitor/output paths need case isolation before
concurrent use. Add bounded monitor input and checkpoint recognition around those
helpers rather than duplicating VM orchestration. Normal-session shared helpers
may check desktop usability only after native login has completed; do not run
qecore-headless preparation where it would enable autologin.

Prefer host input for the first feasibility run because it does not depend on
discovering a pre-login accessibility bus. Fix locale, keyboard and resolution;
wait for identified screen/control checkpoints before each action. A delay or
successful input write is never evidence of a successful screen transition.
Any visual recognition must be calibrated against captured real guest frames,
including negative examples. An unrecognized screen fails at its deadline.

## Management trust boundary

The diagnostic channel is an unresolved security choice, not permission to add
a privileged account. Review a console/guest-agent channel or a narrowly scoped
ephemeral key-only management identity separately, proving it does not count as
a regular user, alter GDM/GIS selection, or change desktop authentication. Until
that proof and approval exist, journal/account assertions remain unimplemented.

## Acceptance cases and evidence

The [checkpoint, controlled-failure and evidence contract](desktop-first-login-cases.md)
defines required assertions, credential handling and retained artifacts. It also
requires repeatable hosted passing and failing runs before blocking rollout.

## Delivery and remaining approvals

1. Review this contract and select the first immutable disk/profile with its
   inspected native journey. Approve the management trust boundary and hosted
   runner capacity; this document does not spend resources or create credentials.
2. Implement the bounded monitor-input feasibility probe with shared helpers;
   prove native surface reachability and credential-safe collection on that disk.
3. Implement the applicable checkpoints and controlled failures, unit-test
   timeouts/recognition/cleanup, then retain repeatable hosted evidence.
4. Only after that evidence, propose suite/workflow interfaces and blocking
   rollout separately. Existing smoke callers retain their current contract.

Test content and reusable GitHub Actions code belong in testsuite; lab resources
belong in projectbluefin/lab. No runtime coverage box in #1026 is checked by
merging this design alone.
