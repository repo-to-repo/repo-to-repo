# Repo-To-Repo

__This is currently a work-in-progress. Changes and PRs welcome!__

## Purpose

How many times have you found a great tool, script or service on Github, but
the install instructions start with "download this binary", or worse yet,
"install the .deb package in releases".

That might work for Windows users, but Linux users deserve more... and this
tool intends to help.

By creating a cronjob to run this script, it will poll the releases of each
github repository, look for updates, and build Debian or RedHat packages and
the other tooling required to turn this into a repository that you can use
with `apt`, `yum` and `dnf`.

## How to use

__Note that this is the work-in-progress instructions, there will be better
documents once the script is complete.__

1. Clone this repository
2. Copy `example.config.json` to `config.json` and [edit
it](#explaining-the-config-file).
3. Run `main.py`.
4. ...
5. Profit? (the script thus far only builds a `.deb` file and doesn't do more)

## Explaining the Config File

The config file is a JSON file with a set of key-value pairs. These are:

* `owner`: The name of the owner or organisation that the repository belongs
to.
* `repo`: The name of the project to get the releases from.
* `version_match`: The string to match at the start of the release, for example
if you only wanted to track version `1.x.x` of a release train, then you could
specify this as `v1.`, or perhaps you want anything matching `1.2.x` then you'd
specify `1.2.`. Also some repos track multiple threads, e.g. `gui-` and `cli-`.
In this case, you might specify `gui-` here to only look for those tagged
releases.
* `object_regex`: A regex to match looking for the release name. This could be
as simple as `.*_linux` or more complex, like
`programme_v\d+\.\d+\.\d+_linux_amd64\.tar\.gz`.
* `path`: Mostly for use during debugging, this is the output of the created
packages, ready for turning into a repo. Eventually it will also be the
location of the final repo.
* `debug`: Produce more logs when defined and set to `true` with any
capitalisation.

### Packaging Configuration Options

If the file is a binary or a compressed file, this script can package it up
automatically into a Debian or RedHat package. To do that, it needs certain
other values, such as:

* `target_binary`: The name of the binary you expect to run.
* `architecture`: (Default: all/noarch) The name of the architecture that the
package manager expects. Some automatic handling of amd64 <-> x86_64 and so on
may occur.
* `maintainer`: (Optional) The name and email address of the package 
maintainer, to be used for corporate deployments (for example). Defaults to the
`owner` value, turned into the required format.
* `description`: (Optional) A description of the output package.
* `dependency`: (Optional) A list of the dependencies

#### Format Specific Options: Debian

Some values can be automatically calculated or defaults supplied, but these are
the Debian specific options:

* `deb_architecture`: (Default: value of `{architecture}` value) Some specific
edge cases are noted (e.g. `all` in Debian packages is recorded as `noarch` in
RedHat packages).
* `deb_codename`: (Default: value of `{repo}/{owner}`) The specific type of
package release this is terminating this should be applied to. When talking
about specific distribution releases, this could be listed as the codename for
that release, e.g. `jammy` or `wheezy`, however in this case, it will be the
name of the particular package type that is being tracked.
* `deb_component`: (Default: `latest`) The types of packages found in this
repository, usually like `main`, `restricted` etc. In this case, it should be
redefined as the particular release to be tracked, e.g. "v1.27" or "v5.x". By
default, it is set to the keyword `latest`. A possible change later would be to
make this pick up details from the `{version_match}` value.

### Autocompletion

Currently this only supports Bash shells, but, defining `autocomplete_bash`
will create a text file in `/etc/bash_completion.d` with the name of the
package and the content as the value of that string.

## Want to contribute?

Thanks for your interest in this project! If you want to fix small typos or
small errors in code, please do so! You will be very welcome!

If you want to make a big change, please raise an issue first explaining what
you want to change, so that we can discuss whether it's something I want to
take forward. I'll probably say yes, but this currently scratches a particular
itch for me, and if it doesn't then I might ask you to fork this into your own
project. Either way... Please get in touch!

## Found a security issue?

Please email me directly; [jon@sprig.gs](mailto:jon@sprig.gs)
