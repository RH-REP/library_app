# Git Remote Usage Note

ArtifactForge is intended to be downloaded or cloned as software, then used as a separate user project repository.

## Intended Remote Layout

A user project should not push back to the ArtifactForge source repository.

Use two Git remotes:

```text
origin    = the user's own project repository
upstream  = the ArtifactForge source repository, fetch-only
```

The user may choose any repository name for `origin`.

## Initial Setup After Clone

After cloning ArtifactForge into a new project directory:

```sh
git remote rename origin upstream
git remote set-url --push upstream DISABLED

git remote add origin <USER_PROJECT_REPOSITORY_URL>
git push -u origin main
```

Expected remote shape:

```text
origin    <USER_PROJECT_REPOSITORY_URL>      (fetch)
origin    <USER_PROJECT_REPOSITORY_URL>      (push)
upstream  <ARTIFACTFORGE_REPOSITORY_URL>     (fetch)
upstream  DISABLED                           (push)
```

## Normal Use

Users commit and push their work only to `origin`:

```sh
git push origin main
```

The user-facing work grows in:

```text
main_artifact/
sub_artifact/
issue_log/
```

ArtifactForge engine files live under:

```text
.core_program/
```

## Updating ArtifactForge

ArtifactForge updates are pulled only when the user intentionally wants to update the engine/template:

```sh
git fetch upstream
git merge upstream/main
git push origin main
```

Safer update workflow:

```sh
git switch -c update-artifactforge
git fetch upstream
git merge upstream/main
# review and test
git switch main
git merge update-artifactforge
git push origin main
```

## Design Intent

- ArtifactForge source is the update source, not the user's push destination.
- User projects are independent repositories with arbitrary names.
- User work and generated artifacts should belong to the user's repository.
- ArtifactForge updates should be deliberate and reviewable.
- The ArtifactForge source repository should also protect its default branch and avoid granting normal users write access.
