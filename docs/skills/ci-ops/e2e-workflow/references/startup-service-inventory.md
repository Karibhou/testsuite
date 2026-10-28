---
name: startup-service-inventory
description: "Which units the fast e2e lane masks, why, and which ones still need a startup-qualification lane."
metadata:
  type: reference
  audience: agents
  maturity: draft
---
# Startup-service inventory

The fast hosted lane in `.github/workflows/e2e.yml` masks units before first
boot, through `systemd.mask=` in `KERNEL_ARGS` and through `/dev/null`
symlinks in each deployment's `/etc/systemd/system/`. A green fast-lane run
therefore says nothing about those units. `startup_service_inventory.yaml`
(repo root) classifies every masked unit:

| Category | Meaning | Fast-lane result counts as qualification? |
|---|---|---|
| `startup_contract` | Shipped first-boot, update or health path that a profile enables | No. Needs a representative startup lane (#1025) |
| `vm_inapplicable` | Needs hardware or a radio hosted QEMU lacks | Not applicable |
| `ci_noise` | Shipped background service outside first boot, masked for speed | No, but not a startup gap |

`tests/unit/test_startup_service_inventory.py` fails when a unit is masked
without an entry, when an entry is no longer masked, or when an entry's
`mask_sites` disagree with the workflow. Changing a mask in `e2e.yml` means
updating the inventory in the same PR.

## Gotchas found while building the inventory

- The symlink loop appends `.service`, `.socket`, `.path` and `.timer` to every
  token. A bare token (`cups`) already masks `cups.socket` and `cups.path`;
  dotted tokens (`cups.path`, `avahi-daemon.socket`) only create bogus
  `*.path.service` names.
- `cups.browsed.service` is not a real unit. Fedora ships
  `cups-browsed.service`, which neither mask site touches.
- Bluefin and Bluefin LTS enable `podman-auto-update.timer` with
  `systemctl --global`, i.e. for user managers. Both mask sites act on the
  system manager, so the shipped user timer is probably still active. Observe
  the user unit before claiming it is covered or masked.
- The fast lane replaces `flatpak-preinstall.service` with a runner-cached
  sideload of `flatpak-app-list.txt`, and `brew-setup.service` with direct
  `brew install`/dnf installs. Those substitutes must not satisfy startup
  assertions.

## Still open (#1025)

The representative startup lane itself (new job or input, bounded deadlines
per `startup_contract` unit, Flatpak remotes/apps/permissions from the shipped
preinstall, greenboot with a real boot-counting path per #706) is a new CI
lane and needs maintainer design approval before implementation.
