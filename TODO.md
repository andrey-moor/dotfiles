# TODO

## Firefox Microsoft Entra SSO

Enable Microsoft Entra SSO in Firefox for corporate single-sign-on (Intune compliance).

**Source:** https://gist.github.com/greghaskins/2a6760ec80c3fd2f32ce969c83b8fc7e
**Policy docs:** https://mozilla.github.io/policy-templates/#microsoftentrasso

### Linux (rocinante, stargazer)

Create `/etc/firefox/policies/policies.json`:

```json
{
  "policies": {
    "MicrosoftEntraSSO": true
  }
}
```

```sh
sudo mkdir -p /etc/firefox/policies
echo '{"policies":{"MicrosoftEntraSSO":true}}' | sudo tee /etc/firefox/policies/policies.json
```

Verify: restart Firefox, check `about:policies`.

### macOS (behemoth)

```sh
defaults write ~/Library/Preferences/org.mozilla.firefox EnterprisePoliciesEnabled -bool TRUE
defaults write ~/Library/Preferences/org.mozilla.firefox MicrosoftEntraSSO -bool TRUE
```

### Status

- [ ] Test on rocinante
- [ ] If working, integrate into dotfiles (Nix module or chezmoi)
- [ ] Apply to stargazer
- [ ] Apply to behemoth
