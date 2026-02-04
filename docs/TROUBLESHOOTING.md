# Troubleshooting Guide

> **Last updated:** 2026-02-03
> **Applies to:** Stargazer and similar Intune-enrolled Arch Linux ARM VMs on Parallels

Quick diagnosis: Run `intune-health` to identify most common issues automatically.

## Table of Contents

1. [Boot Issues](#boot-issues)
   - [No LUKS Passphrase Prompt](#no-luks-passphrase-prompt)
   - [Limine Boots Instead of GRUB](#limine-boots-instead-of-grub)
   - [Kernel Panic: Unable to Mount Root FS](#kernel-panic-unable-to-mount-root-fs)
   - [Wrong UUID in GRUB Config](#wrong-uuid-in-grub-config)
2. [VM Issues](#vm-issues)
   - [Clone Won't Start](#clone-wont-start)
   - [Shared Folders Not Visible](#shared-folders-not-visible)
   - [No Network After Reboot](#no-network-after-reboot)
3. [Rosetta and Nix Issues](#rosetta-and-nix-issues)
   - [Rosetta binfmt Not Registered](#rosetta-binfmt-not-registered)
   - [x86_64 Binaries Fail to Execute](#x86_64-binaries-fail-to-execute)
   - [Nix Build Fails for x86_64 Packages](#nix-build-fails-for-x86_64-packages)
4. [Intune Issues](#intune-issues)
   - [Device Broker Fails with D-Bus Error](#device-broker-fails-with-d-bus-error)
   - [Enrollment Fails with Keyring Error](#enrollment-fails-with-keyring-error)
   - [Portal Shows Blank Screen](#portal-shows-blank-screen)
   - [Authentication Fails](#authentication-fails)
5. [YubiKey Issues](#yubikey-issues)
   - [YubiKey Not Detected](#yubikey-not-detected)
   - [Certificate Not Shown in Picker](#certificate-not-shown-in-picker)
   - [PIN Rejected](#pin-rejected)

---

## Quick Diagnosis

Before diving into specific issues, run:

```bash
intune-health
```

This checks all critical components and provides hints for failures. Exit code 0 = all critical checks pass.

For more detail:

```bash
intune-health --verbose
intune-logs --all | tail -50
```

---
