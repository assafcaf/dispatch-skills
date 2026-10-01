#!/usr/bin/env bash
# Install the delivery workflow into a project, and write its per-project configuration.
#
# The skills and agents read everything project-specific from .claude/workflow/config.md —
# which tracker, which project, which commands. That file cannot ship filled in, so this asks
# and writes it. Everything it asks can be answered up front with a flag instead, which is
# what makes an unattended install possible. /setup-workflow, run inside Claude Code
# afterwards, discovers the rest (statuses, transition ids) and checks the whole setup.
#
#   bash install.sh [options]
#
#     --project <path>      project to install into            (default: current directory)
#     --tracker <kind>      jira | github | local              (asked if not given)
#     --key <PROJ>          issue key prefix, e.g. PROJ        (jira)
#     --jira-site <name>    the <name> in <name>.atlassian.net (jira)
#     --jira-cloud-id <id>  Jira cloud id, blank if unknown    (jira)
#     --gh-repo <o/r>       owner/repo                         (github; defaults from `gh`)
#     --no-config           install the files, write no config
#     --force               overwrite existing files without keeping a .bak
#     --dry-run             print every action, change nothing
#
# Files that are yours once written — .claude/workflow/config.md, .claude/settings.json,
# .claude/agents/tracker.md, docs/decisions/README.md — are never overwritten. Delete one to
# have it regenerated.
#
# Re-running is safe: identical files are skipped.
#
# Run from a git checkout of PAD, it records the commit in .claude/workflow/pad.lock, which is
# where /pad-update starts from. From a packaged copy the commit is unknown and no lock is
# written; /pad-update then finds the commit by comparing files.

set -u

SELF="dispatch-skills"
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/payload"

project="$PWD"
tracker=""
jira_site=""
jira_cloud=""
key=""
gh_repo=""
do_config=yes
force=no
dry=no
changed=0
skipped=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)       project="${2-}"; shift 2 ;;
    --tracker)       tracker="${2-}"; shift 2 ;;
    --jira-site)     jira_site="${2-}"; shift 2 ;;
    --jira-cloud-id) jira_cloud="${2-}"; shift 2 ;;
    --key)           key="${2-}"; shift 2 ;;
    --gh-repo)       gh_repo="${2-}"; shift 2 ;;
    --no-config)     do_config=no; shift ;;
    --force)         force=yes; shift ;;
    --dry-run)       dry=yes; shift ;;
    -h|--help)       sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf '%s: unknown option %s\n' "$SELF" "$1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
act()  { if [ "$dry" = yes ]; then printf '  would %s\n' "$*"; else printf '  %s\n' "$*"; fi; }
warn() { printf '%s: %s\n' "$SELF" "$*" >&2; }
die()  { warn "$1"; exit 1; }

[ -d "$SRC" ] || die "payload missing: $SRC"
[ -d "$project" ] || die "no such directory: $project"
project="$(cd -- "$project" && pwd)"

case "$tracker" in ''|jira|github|local) ;; *)
  die "--tracker must be jira, github or local (got '$tracker')" ;;
esac

say "$SELF -> $project"

# --- Files that track upstream: updated on reinstall, with a .bak of any local edit ------
install_file() { # install_file <payload-rel> <project-rel>
  local src="$SRC/$1" dst="$project/$2"
  [ -f "$src" ] || { warn "missing from payload: $1"; return 1; }

  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    skipped=$((skipped + 1)); return 0
  fi
  if [ -f "$dst" ] && [ "$force" = no ] && [ ! -f "$dst.bak" ]; then
    act "back up $2 -> $2.bak"
    [ "$dry" = yes ] || cp "$dst" "$dst.bak" || return 1
  fi
  act "install $2"
  if [ "$dry" = no ]; then
    mkdir -p "$(dirname "$dst")" || return 1
    cp "$src" "$dst" || return 1
    case "$2" in *.sh) chmod +x "$dst" ;; esac
  fi
  changed=$((changed + 1))
}

# --- Files that are the project's once written: created once, never overwritten -----------
install_once() { # install_once <project-rel> <writer-command...>
  local rel="$1"; shift
  if [ -f "$project/$rel" ]; then
    say "  keeping existing $rel (delete it to regenerate)"
    skipped=$((skipped + 1)); return 0
  fi
  act "write $rel"
  if [ "$dry" = no ]; then
    mkdir -p "$(dirname "$project/$rel")" || return 1
    "$@" > "$project/$rel" || return 1
  fi
  changed=$((changed + 1))
}

say ""
say "Skills -> .claude/skills/"
for f in $(cd "$SRC" && find claude/skills -type f | sort); do
  install_file "$f" ".${f}"
done

say ""
say "Agents -> .claude/agents/"
# tracker.md is per project (its tools depend on the tracker), so it is written below.
for f in $(cd "$SRC" && find claude/agents -type f ! -name tracker.md | sort); do
  install_file "$f" ".${f}"
done

say ""
say "Workflow -> .claude/workflow/"
# All of it tracks upstream. config.example.md is also the template config.md is written from
# below; it is installed too, because /setup-workflow upgrade adds missing sections from it.
for f in $(cd "$SRC" && find claude/workflow -type f | sort); do
  install_file "$f" ".${f}"
done
install_file "claude/statusline.py" ".claude/statusline.py"

say ""
say "Workflows -> .claude/workflows/"
for f in $(cd "$SRC" && find claude/workflows -type f | sort); do
  install_file "$f" ".${f}"
done

# --- The PAD commit these files came from --------------------------------------------------
# /pad-update merges from the commit recorded here. Only a clean git checkout knows its commit;
# a lock left by an earlier install no longer describes the files just written, so it goes.
write_lock() {
  local root="$SRC/.." lock=".claude/workflow/pad.lock" commit="" source_url last
  if git -C "$root" rev-parse --show-toplevel >/dev/null 2>&1 \
     && [ -z "$(git -C "$root" status --porcelain -- payload 2>/dev/null)" ]; then
    commit="$(git -C "$root" rev-parse --verify --quiet HEAD 2>/dev/null)"
  fi
  if [ -z "$commit" ]; then
    if [ -f "$project/$lock" ]; then
      act "remove $lock (this copy of PAD does not know its commit)"
      [ "$dry" = yes ] || rm -f "$project/$lock"
    fi
    say "  no $lock written: /pad-update finds the commit by comparing files"
    return 0
  fi
  source_url="$(git -C "$root" config --get remote.origin.url 2>/dev/null)"
  last="$(cd "$SRC" && ls migrations 2>/dev/null | grep -E '^[0-9]{4}-.*\.md$' | sort | tail -n 1)"
  [ -n "$last" ] || last="0000"
  act "write $lock"
  [ "$dry" = yes ] || {
    echo "# The PAD commit this project's harness came from. Written by the installer and /pad-update; commit it."
    echo "source: ${source_url:-https://github.com/assafcaf/pad}"
    echo "commit: $commit"
    echo "version: $(tr -d '\r' < "$SRC/claude/workflow/VERSION" | head -n 1 | tr -d '[:space:]')"
    echo "migration: ${last%%-*}"
  } > "$project/$lock"
}

say ""
say "Update lock -> .claude/workflow/pad.lock"
write_lock

say ""
say "Development record -> docs/decisions/"
install_once "docs/decisions/README.md" cat "$SRC/docs/decisions/README.md"

# --- Configuration ------------------------------------------------------------------------
ask() { # ask <prompt> <default> -> echoes the answer
  local prompt="$1" default="${2-}" reply=""
  if [ -t 0 ]; then
    if [ -n "$default" ]; then printf '  %s [%s]: ' "$prompt" "$default" >&2
    else printf '  %s: ' "$prompt" >&2; fi
    read -r reply
  fi
  printf '%s' "${reply:-$default}"
}

default_gh_repo() {
  (cd "$project" && gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) \
    || printf '<owner>/<repo>'
}

render_config() {
  local pad_version
  pad_version="$(tr -d '' < "$SRC/claude/workflow/VERSION" | head -n 1 | tr -d '[:space:]')"
  # `|` as the sed delimiter, because every one of these can contain a slash.
  sed -e "s|<TRACKER>|${tracker}|g" \
      -e "s|<JIRA_SITE>|${jira_site:-<your-site>}|g" \
      -e "s|<JIRA_CLOUD_ID>|${jira_cloud:-<your-cloud-id>}|g" \
      -e "s|<GH_REPO>|${gh_repo:-<owner>/<repo>}|g" \
      -e "s|<KEY>|${key:-PROJ}|g"       -e "s|<PAD_VERSION>|${pad_version}|g" \
      "$SRC/claude/workflow/config.example.md"
}

render_tracker_agent() {
  local tools
  case "$tracker" in
    jira)   tools="Read, mcp__atlassian" ;;
    github) tools="Read, Bash" ;;
    local)  tools="Read, Edit, Write, Glob" ;;
  esac
  sed -e "s|^tools: .*|tools: ${tools}|" "$SRC/claude/agents/tracker.md"
}

ensure_ignored() { # ensure_ignored <pattern>
  local gi="$project/.gitignore"
  if [ -f "$gi" ] && grep -qxF "$1" "$gi"; then return 0; fi
  act "add $1 to .gitignore"
  [ "$dry" = yes ] || printf '%s\n' "$1" >> "$gi"
}

say ""
if [ "$do_config" = no ]; then
  say "Config: skipped (--no-config). Copy .claude/workflow/config.example.md from the payload"
  say "        to .claude/workflow/config.md and fill it in before the first run."
else
  say "Config"
  if [ -z "$tracker" ]; then
    if [ -t 0 ]; then
      say ""
      say "  These skills file work as tickets and keep them current during a run, so they need"
      say "  to know where tickets live. Which does this project use?"
      say "    1) Jira            — via the atlassian MCP server        [default]"
      say "    2) GitHub Issues   — via the gh CLI"
      say "    3) local files     — markdown under .work/tickets/, not committed"
      case "$(ask 'choice' '1')" in
        2) tracker=github ;;
        3) tracker=local ;;
        *) tracker=jira ;;
      esac
    else
      tracker=jira
      say "  not a terminal — assuming --tracker jira; placeholders stay in place"
    fi
  fi

  case "$tracker" in
    jira)
      [ -n "$key" ]        || key="$(ask 'Jira project key (the PROJ in PROJ-12)' 'PROJ')"
      [ -n "$jira_site" ]  || jira_site="$(ask 'Jira site (the <name> in <name>.atlassian.net)' '<your-site>')"
      [ -n "$jira_cloud" ] || jira_cloud="$(ask 'Jira cloud id (Enter: /setup-workflow finds it)' '<your-cloud-id>')"
      ;;
    github)
      [ -n "$gh_repo" ] || gh_repo="$(ask 'GitHub repo (owner/repo)' "$(default_gh_repo)")"
      ;;
  esac

  install_once ".claude/workflow/config.md" render_config
  install_once ".claude/agents/tracker.md" render_tracker_agent

  # Settings carry worktree.baseRef, without which parallel waves branch from the default
  # branch and miss every earlier task. An existing file is the project's, so it is never
  # merged into blindly: the example lands beside it and /setup-workflow does the merge.
  if [ -f "$project/.claude/settings.json" ] \
     && cmp -s "$SRC/claude/settings.example.json" "$project/.claude/settings.json"; then
    skipped=$((skipped + 1))
  elif [ -f "$project/.claude/settings.json" ]; then
    install_file "claude/settings.example.json" ".claude/settings.example.json"
    say "  .claude/settings.json exists — left alone; /setup-workflow merges in the example"
  else
    install_once ".claude/settings.json" cat "$SRC/claude/settings.example.json"
  fi

  for pattern in ".work/" ".claude/worktrees/" "CLAUDE.local.md" ".claude/settings.local.json"; do
    ensure_ignored "$pattern"
  done
fi

# --- Summary ------------------------------------------------------------------------------
say ""
say "Installed: $changed file(s); already current: $skipped"
say ""
say "Next:"
say "  1. Restart Claude Code in this project, then run /setup-workflow. It checks the tracker"
say "     connection, discovers statuses and transition ids, runs the config's commands, and"
say "     installs the status line."
say "  2. Read .claude/workflow/config.md, especially Commands, and make it true of this repo."
say "  3. /spec <idea>  ->  /tickets <spec>  ->  /batch-implement <epic>."
say ""
say "Every skill is user-invoked only (disable-model-invocation), so nothing runs on its own."
