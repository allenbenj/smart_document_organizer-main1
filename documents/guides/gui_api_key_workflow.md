# GUI Launcher API Key Workflow

This document describes the lifecycle, security considerations, and developer workflows for API keys used by the GUI launcher to access backend services. It outlines generation, rotation, revocation, and secure storage practices to ensure secure and reliable operation of the GUI.

## 1) Overview

The GUI launcher relies on API keys to authenticate requests to backend services. API keys should be treated as secrets and rotated regularly to minimize the impact of potential compromises.

## 2) Key Lifecycle

- Generation
- Rotation
- Revocation

## 3) Security and Storage

- Encryption at rest
- Secure in-memory handling
- Persistent storage of key metadata (e.g., label, creation date, expiry)
- OS-level secret storage guidance (Windows Credential Manager, macOS Keychain, Linux Secret Service)

## 4) Roles and Access

- Admins can generate, rotate, and revoke keys
- GUI-access users may request a key issuance if allowed by policy

## 5) GUI Workflows

- Generating a key
- Rotating a key
- Revoking a key

## 6) Usage Scenarios

- Initial setup: generate a default key for the GUI launcher
- Quarterly rotation: rotate keys on a 90-day cadence
- Compromise response: revoke and rotate immediately when compromise is suspected

## 7) Examples

Generate a new API key
- Label: default
- Expiry: 90 days
- Returns: key_reference or token

Rotate an API key
- Label: default
- Steps: generate new key, switch GUI to use new key, revoke old key

Revoke an API key
- Label: default
- Effect: GUI will stop sending requests with the old key

## 8) Troubleshooting

- If the GUI fails to load a key, check the key store and environment configuration
- If rotation fails, verify permissions and secret storage access

## 9) References

- security best practices
- OS secret storage guidelines