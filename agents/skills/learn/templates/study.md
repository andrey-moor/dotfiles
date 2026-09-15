---
title: How a DNS lookup resolves
goal: understand name resolution well enough to debug it
sources: [RFC 1034, RFC 1035, RFC 2308]
date: 2026-09-14
---
<!-- Shape example. Its facts come from public RFCs. A real lesson teaches from its notes/ folder and cites it in Go deeper. -->

# Gist

A DNS lookup turns a name such as www.example.com into an IP address. It exists because people remember names and networks route by address. Your machine asks one question of a recursive resolver. That resolver walks down from the root servers, one referral at a time, until the domain's own server answers. Answers are cached for as long as the domain owner allows, so most lookups never leave the resolver.

**Remember:** the recursive resolver does the walking. Your machine asks once and waits.

# Mechanism

<!-- A step-mode figure goes here, one data-step per worked-example step:
![The questions one lookup asks, from laptop to the domain's own server](figure.html) -->

The laptop asks one question. The recursive resolver asks up to three more, and each server it asks points it one level closer to the answer.

# Worked example

These values are illustrative: a laptop looks up `www.example.com` through a resolver whose cache is empty, and the answer carries a TTL of 3,600 seconds.

## Step 1: The laptop asks its resolver

The laptop's stub resolver sends one recursive query for `www.example.com` to the resolver its network configured. It then waits for a final answer or an error.

## Step 2: The resolver asks a root server

The resolver's cache is empty, so it starts at the top. It asks a root server, which does not know the address but knows who runs `.com`.

## Step 3: The root refers it to .com

The root server replies with a referral: the names and addresses of the `.com` servers. The resolver caches that referral and asks one of them.

## Step 4: The .com servers refer it to example.com

The `.com` server does not hold the address either. It refers the resolver to the servers that are authoritative for `example.com`.

## Step 5: The authoritative server answers

The authoritative server returns the address record with its TTL of 3,600 seconds. The resolver caches it for that long and sends the answer to the laptop.

# Parts

## Stub resolver

**What:** the small client on your machine that sends lookups to a configured resolver. **Why:** walking the tree needs a cache and retries that every device would otherwise repeat. **Without it:** each application would carry its own DNS logic. **Remember:** it asks for recursion and trusts the answer it gets.

### Details

Queries go to port 53, usually over UDP. A classic UDP message is limited to 512 bytes, and a longer answer is retried over TCP (RFC 1035, sections 4.2.1 and 4.2.2).

## Recursive resolver

**What:** the server that answers on your behalf by following referrals and caching what it learns. **Why:** one shared cache serves many clients and spares the servers above it. **Without it:** every lookup would start at the root. **Remember:** it caches referrals as well as answers.

### Details

A resolver also caches failures. A name that does not exist is remembered for a time the zone sets, which RFC 2308 calls negative caching.

## Root and TLD servers

**What:** the servers at the top of the tree that hold referrals, not final answers. **Why:** delegation lets each level run its own part of the namespace. **Without it:** one database would have to hold every name. **Remember:** a referral says who to ask next.

### Details

A referral lists the child zone's name servers. When those servers sit inside the child zone, the referral also carries their addresses so the resolver can reach them (RFC 1034, section 4.2.1).

## Authoritative server

**What:** the server that holds the zone's records and gives final answers. **Why:** the domain owner controls the records and how long others may cache them. **Without it:** there is nothing for the referrals to point at. **Remember:** the TTL it sets decides how fast a change reaches users.

### Details

A TTL is a time in seconds that tells caches how long a record stays valid (RFC 1035, section 3.2.1).

# Misconceptions

- **My computer walks the DNS tree itself.** Almost never. The stub resolver asks for recursion, and the recursive resolver does the walking.
- **A changed record takes effect at once.** Caches keep the old record until its TTL runs out, so a change reaches users gradually.

# Check yourself

## Q: What does the stub resolver ask, and whom?

It asks the configured recursive resolver one recursive question and waits for a final answer or an error.

## Q: Why does the resolver start at the root only when its cache is empty?

Its cache already holds referrals and answers from earlier lookups. It starts from the lowest level it knows about.

## Q: Why does the reply from the .com servers not contain the address?

Those servers hold delegations, not records for `example.com`. They can only say which servers do.

## Q: Why do records carry a TTL instead of staying valid forever?

Owners need changes to reach users eventually. The TTL bounds how long any cache may serve an old record.

## Q: An owner lowers a one-day TTL to five minutes an hour before a migration. Why does that not help?

Resolvers that cached the record under the one-day TTL keep it for up to a day. Lower the TTL at least one old TTL ahead of the change.

## Q: What breaks if every laptop walked the tree itself?

Load on root and TLD servers multiplies, no cache is shared, and each lookup takes several round trips instead of one.

# Glossary

- **stub resolver**: the client on a machine that sends recursive queries to a configured resolver.
- **recursive resolver**: a server that follows referrals and caches results on behalf of clients.
- **authoritative server**: a server that holds a zone's records and gives final answers for it.
- **referral**: a reply that names the servers to ask next instead of answering.
- **TTL**: the number of seconds a cache may keep a record.
- **TLD**: a top-level domain such as .com.

# Go deeper

- [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034): the concepts behind the namespace, delegation, and resolvers.
- [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035): message formats, transport, and record fields.
- [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308): negative caching.
