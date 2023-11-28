# Repo-to-Repo

A tool for turning binary file releases into package repositories.

## Why does this project exist?

Repo-to-Repo was born out of exasperation with (mostly) Kubernetes projects who
will typically release a binary executable file in Github, but not provide a
packaged release. This means that updates are unable to be tracked and
installation instructions vary between tools, target operating systems and
understanding.

This tooling also means that there's no expectation on the projects, teams or
individuals running the repositories to support your operating system or
distribution of choice. You can just build your own packager.

For individuals, running a Cronjob to refresh the package creation service is
a good idea, as it's similar in effect to what you're likely already doing with
your package manager, and that can "just" collect the results. For
organisations, this is HUGE, as now you can reliably collect all the
binary-release tools your team uses, and build it into your base image creation
tooling (like Hashicorp Packer), or your automatic deployment tooling (like
Ansible from RedHat or Puppet from Perforce).

## What state is the project in?

Currently, this project should be considered to be pre-MVP. Debian packages and
repositories are created, but RPM based repositories and packages are not
currently supported at all. As a pre-MVP, configurations and file structures
are near-guaranteed to change between one development iteration and the next.

In addition, this script currently only understands binary file releases or
DEB file releases. While the example file lists `.tar.gz` or `.tgz` objects to
consume, these are currently entirely unhandled (beyond creating a DEB package
which contains that compressed file stored as the "target binary" filename).

It is currently unlicensed, although it may end up being released under an MIT
or BSD-0 Clause license.

## How do I use it?

### Get the script

Clone the repository and create a configuration file. A sample configuration
file is included as [`example.config.json`](examples/example.config.json).

Note that this example file will put your output repositories in `/tmp/output`.
This script does not handle putting the public key anywhere!

### Create a GPG Key

Create a GPG Key to sign the packages or package lists. There is a sample
[`pgp-key.batch`](examples/pgp-key.batch) file, which should be customized and
used to create a new GPG key, using this set of commands:

```bash
export GNUPGHOME="$(mktemp -d /tmp/pgpkeys-XXXXXX)"
gpg --no-tty --batch --gen-key pgp-key.batch
gpg --armor --export "Repo-To-Repo Packager" > public.asc
gpg --armor --export-secret-keys "Repo-To-Repo Packager" > private.asc
rm -Rf "$GNUPGHOME"
```

### Install dependencies

Run `pip -r requirements.txt`. I'd recommend doing this in a virtual
environment with `virtualenv`.

### Run me

Then run
`repo_to_repo.py --config config.json --pgp-key private.asc`

### Consume me in Debian based distributions

Copy the private key to the consuming device (typically now in
`/etc/apt/keyrings/YOUR_REPO_NAME.asc`) and create a source file
containing the following content:

```deb
deb [arch=amd64 signed-by=/etc/apt/keyrings/YOUR_REPO_NAME.asc] https://example.org/deb misc main
```

In this example, `YOUR_REPO_NAME` might be `repo-to-repo`, while
`https://example.org/deb` might be the server in which you host the output of
the script, which might have been generated to `/tmp/output/latest/deb/`.
`misc` relates to the name of the directories directly under `deb/pool` while
`main` relates to the subdirectory under that one.

If no "suite" or codename (e.g. `misc`), or no component or archive (e.g.
`main`) are specified then `misc` and `main` are the values which will be used.

Run `sudo apt update` and then `sudo apt install YOUR_PACKAGE_NAME` to use the
assets downloaded in the repo.
