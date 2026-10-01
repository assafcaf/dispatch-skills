#!/usr/bin/env bash
# Bring a project's installed PAD harness up to a newer PAD commit, keeping the project's edits.
#
#   pad-update.sh [--pad <clone>] [--project <dir>] [--to <ref>] [--base <sha>] [--dry-run]
#   pad-update.sh --find-base [--pad <clone>] [--project <dir>] [--to <ref>]
#   pad-update.sh --record    [--pad <clone>] [--project <dir>] [--to <ref>]
#
#     --pad <clone>    a git clone of PAD, with history   (default: the clone this script is in)
#     --project <dir>  the project to update              (default: the repo around the cwd)
#     --to <ref>       the PAD commit to update to        (default: the clone's HEAD)
#     --base <sha>     the PAD commit the project's files came from, for a project that has no
#                      .claude/workflow/pad.lock yet. With a lock, the lock's commit is the base.
#     --dry-run        print every action, change nothing
#
# Run it from a fresh PAD clone, not from the copy installed in the project: the installed copy
# is the old updater, and its own directory holds no PAD history.
#
# Update. For every file PAD ships under payload/claude/ at the base or at the target, with
# old = PAD at the base, new = PAD at the target, mine = the project's copy:
#
#   REPLACE   mine is old, new differs               -> new
#   KEEP      mine differs from old, new is old      -> mine stays
#   MERGE     both changed, `git merge-file` is clean
#   CONFLICT  both changed and the merge left conflict markers in the file; or PAD deleted a
#             file this project changed (kept); or both added it with different content
#   ADD       new upstream, absent here              -> new (a new .sh is staged as executable)
#   DELETE    deleted upstream, mine is old          -> removed
#   GONE      shipped at the base, removed here      -> stays removed
#
# Files already equal to new print nothing. The project's own files are never touched:
# config.md, settings.json, agents/tracker.md, docs/decisions/. Line endings are compared and
# written as LF.
#
# After the files: `SETTINGS ...` when PAD's settings.example.json changed between base and
# target, one `MIGRATION <path>` per note in payload/migrations/ numbered above the lock's
# `migration:` (above the base's highest, when there is no lock), and a `SUMMARY` line. The
# last line is `UPDATE OK` (exit 0) or `UPDATE CONFLICTS <n>` (exit 1). The lock is not
# written: run --record once the conflicts, the migrations and the checks are done.
#
# --find-base scores each PAD commit up to the target by how many of its payload files this
# project holds unchanged, and prints `BASE <sha> <matched>/<files>` for the best one (the
# newest on a tie), exit 0. When fewer than half of that commit's files match, it prints
# `BASE NONE <sha> <matched>/<files>` and exits 1: name the base yourself.
#
# --record writes .claude/workflow/pad.lock for the target: `source:`, `commit:`, `version:`
# and `migration:` (the highest note number at the target).
#
# Exit 2: no PAD clone, no project, an unknown ref, or no base. Exit 64: usage.

set -uo pipefail

usage() { sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 64; }
die() { echo "pad-update: $*" >&2; exit 2; }

pad=""
project=""
to="HEAD"
base=""
dry=""
mode="update"
while [ $# -gt 0 ]; do
  case "$1" in
    --pad)       pad="${2-}"; shift 2 || usage ;;
    --project)   project="${2-}"; shift 2 || usage ;;
    --to)        to="${2-}"; shift 2 || usage ;;
    --base)      base="${2-}"; shift 2 || usage ;;
    --dry-run)   dry=1; shift ;;
    --find-base) mode="find-base"; shift ;;
    --record)    mode="record"; shift ;;
    *) usage ;;
  esac
done

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -n "$pad" ] || pad="$(git -C "$bin" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$pad" ] && [ -d "$pad" ] || die "no PAD clone: pass --pad <clone>"
p() { git -C "$pad" "$@"; }

target="$(p rev-parse --verify --quiet "$to^{commit}" 2>/dev/null)" ||
  die "$to is not a commit in $pad"
[ -n "$(p ls-tree "$target" -- payload/claude 2>/dev/null)" ] ||
  die "$pad has no payload/ at $to: run this from a PAD clone, or pass --pad <clone>"

[ -n "$project" ] || project="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$project" ] && [ -d "$project" ] || die "no project: pass --project <dir>"
project="$(cd "$project" && pwd)"
lock="$project/.claude/workflow/pad.lock"

# The payload files that track upstream at a commit, as project-relative paths. tracker.md is
# written per project and settings.example.json is merged by hand, so neither is listed.
tracked() { # tracked <commit>
  p ls-tree -r --name-only "$1" -- payload/claude 2>/dev/null | tr -d '\r' |
    sed -n 's|^payload/claude/|.claude/|p' |
    grep -v -x -e '.claude/agents/tracker.md' -e '.claude/settings.example.json'
}

lock_field() { # lock_field <name>
  [ -f "$lock" ] || return 0
  sed -n "s/^$1:[[:space:]]*//p" "$lock" | head -n 1 | tr -d '\r'
}

migrations() { # migrations <commit> -> the notes' paths, in number order
  p ls-tree --name-only "$1" -- payload/migrations/ 2>/dev/null | tr -d '\r' |
    grep -E '^payload/migrations/[0-9]{4}-[^/]*\.md$' | sort
}

highest_migration() { # highest_migration <commit> -> NNNN, 0000 when there are none
  local last
  last="$(migrations "$1" | tail -n 1)"
  last="${last#payload/migrations/}"
  [ -n "$last" ] && printf '%s' "${last%%-*}" || printf '0000'
}

tmp="$(mktemp -d)" || die "cannot make a temporary directory"
trap 'rm -rf "$tmp"' EXIT

# --- --find-base --------------------------------------------------------------------------
if [ "$mode" = "find-base" ]; then
  # Hash the project's copy of every file PAD has ever shipped, once, as git would store it.
  : > "$tmp/mine"
  for src in $(p log --format= --name-only "$target" -- payload/claude | tr -d '\r' | sort -u); do
    path=".claude/${src#payload/claude/}"
    [ -f "$project/$path" ] || continue
    sha="$(tr -d '\r' < "$project/$path" | p hash-object --stdin)" || continue
    printf '%s\t%s\n' "$sha" "$src" >> "$tmp/mine"
  done

  best=""
  best_matched=-1
  best_total=0
  for c in $(p log --format=%H "$target" -- payload/claude); do
    score="$(p ls-tree -r "$c" -- payload/claude | tr -d '\r' | awk -F '\t' '
      NR == FNR { mine[$2] = $1; next }
      $2 == "payload/claude/agents/tracker.md" || $2 == "payload/claude/settings.example.json" { next }
      { total++; split($1, meta, " "); if (mine[$2] == meta[3]) matched++ }
      END { printf "%d %d", matched, total }' "$tmp/mine" -)"
    matched="${score%% *}"
    total="${score##* }"
    if [ "$matched" -gt "$best_matched" ]; then
      best="$c"; best_matched="$matched"; best_total="$total"
    fi
  done

  [ -n "$best" ] || die "$pad has no commits that touch payload/claude"
  if [ "$best_total" -eq 0 ] || [ $((best_matched * 2)) -lt "$best_total" ]; then
    echo "BASE NONE $best $best_matched/$best_total"
    exit 1
  fi
  echo "BASE $best $best_matched/$best_total"
  exit 0
fi

# --- --record -----------------------------------------------------------------------------
if [ "$mode" = "record" ]; then
  source_url="$(lock_field source)"
  [ -n "$source_url" ] || source_url="$(p config --get remote.origin.url 2>/dev/null)"
  [ -n "$source_url" ] || source_url="https://github.com/assafcaf/pad"
  version="$(p show "$target:payload/claude/workflow/VERSION" 2>/dev/null | tr -d '\r' | head -n 1)"
  if [ -n "$dry" ]; then
    echo "would record $target in .claude/workflow/pad.lock"
    exit 0
  fi
  mkdir -p "$(dirname "$lock")" || die "cannot write $lock"
  {
    echo "# The PAD commit this project's harness came from. Written by the installer and /pad-update; commit it."
    echo "source: $source_url"
    echo "commit: $target"
    echo "version: $version"
    echo "migration: $(highest_migration "$target")"
  } > "$lock" || die "cannot write $lock"
  echo "RECORDED $target"
  exit 0
fi

# --- update -------------------------------------------------------------------------------
from_lock=""
if [ -z "$base" ]; then
  base="$(lock_field commit)"
  from_lock=1
fi
[ -n "$base" ] ||
  die "no base: $lock is missing. Run --find-base, then pass the commit it names as --base"
base_sha="$(p rev-parse --verify --quiet "$base^{commit}" 2>/dev/null)" ||
  die "the base $base is not a commit in $pad"
base="$base_sha"

replaced=0; kept=0; merged=0; added=0; deleted=0; gone=0; same=0; conflicts=0

put() { # put <content file> <project-rel path>: write the file, LF, scripts executable
  [ -z "$dry" ] || return 0
  mkdir -p "$(dirname "$project/$2")" && cp "$1" "$project/$2" || die "cannot write $2"
  case "$2" in *.sh) chmod +x "$project/$2" ;; esac
}

for path in $( { tracked "$base"; tracked "$target"; } | sort -u ); do
  src="payload/claude/${path#.claude/}"
  o=""; n=""; m=""
  if p show "$base:$src" 2>/dev/null | tr -d '\r' > "$tmp/old"; then o=1; else : > "$tmp/old"; fi
  if p show "$target:$src" 2>/dev/null | tr -d '\r' > "$tmp/new"; then n=1; else : > "$tmp/new"; fi
  if [ -f "$project/$path" ]; then tr -d '\r' < "$project/$path" > "$tmp/mine"; m=1; else : > "$tmp/mine"; fi

  if [ -z "$n" ]; then                                   # deleted upstream
    if [ -z "$m" ]; then
      :
    elif cmp -s "$tmp/old" "$tmp/mine"; then
      echo "DELETE $path"
      [ -n "$dry" ] || rm -f "$project/$path"
      deleted=$((deleted + 1))
    else
      echo "CONFLICT $path deleted upstream, changed here: kept"
      conflicts=$((conflicts + 1))
    fi
  elif [ -z "$m" ]; then                                 # absent here
    if [ -n "$o" ]; then
      echo "GONE $path shipped at the base, removed here: left out"
      gone=$((gone + 1))
    else
      echo "ADD $path"
      put "$tmp/new" "$path"
      # git on Windows records a new file as 100644; stage a new script as executable.
      case "$path" in *.sh)
        [ -n "$dry" ] || git -C "$project" add --chmod=+x -- "$path" >/dev/null 2>&1 || true ;;
      esac
      added=$((added + 1))
    fi
  elif cmp -s "$tmp/new" "$tmp/mine"; then
    same=$((same + 1))
  elif [ -n "$o" ] && cmp -s "$tmp/old" "$tmp/mine"; then
    echo "REPLACE $path"
    put "$tmp/new" "$path"
    replaced=$((replaced + 1))
  elif [ -n "$o" ] && cmp -s "$tmp/old" "$tmp/new"; then
    echo "KEEP $path changed here, unchanged upstream"
    kept=$((kept + 1))
  else                                                   # both changed, or both added
    if git merge-file -L "this project" -L "PAD ${base:0:7}" -L "PAD ${target:0:7}" \
         "$tmp/mine" "$tmp/old" "$tmp/new" >/dev/null 2>&1; then
      echo "MERGE $path"
      merged=$((merged + 1))
    else
      echo "CONFLICT $path changed here and upstream: conflict markers left in the file"
      conflicts=$((conflicts + 1))
    fi
    put "$tmp/mine" "$path"
  fi
done

settings="payload/claude/settings.example.json"
if [ "$(p rev-parse --quiet --verify "$base:$settings" 2>/dev/null)" != \
     "$(p rev-parse --quiet --verify "$target:$settings" 2>/dev/null)" ]; then
  echo "SETTINGS $settings changed upstream: .claude/settings.json is the project's, propose the difference"
fi

applied="$(highest_migration "$base")"
if [ -n "$from_lock" ]; then
  recorded="$(lock_field migration)"
  [ -z "$recorded" ] || applied="$recorded"
fi
for note in $(migrations "$target"); do
  number="${note#payload/migrations/}"
  number="${number%%-*}"
  [ $((10#$number)) -gt $((10#$applied)) ] && echo "MIGRATION $note"
done

echo "SUMMARY ${base:0:7}..${target:0:7} replaced=$replaced merged=$merged added=$added deleted=$deleted kept=$kept gone=$gone unchanged=$same conflicts=$conflicts"
if [ "$conflicts" -eq 0 ]; then echo "UPDATE OK"; exit 0; fi
echo "UPDATE CONFLICTS $conflicts"
exit 1
