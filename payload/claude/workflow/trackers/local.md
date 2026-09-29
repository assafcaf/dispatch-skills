# Tracker adapter: local files

For repos without a tracker, or for work you don't want in one. Tickets are Markdown files
under `.work/tickets/` (gitignored), so they stay on this machine.

**The ledger lives in the main checkout,** the parent of `git rev-parse --git-common-dir`, not
the current directory. A worktree has its own empty `.work/`, so resolving from the cwd there
finds no tickets or writes stray copies. Without a shell: in a worktree, `.git` is a file that
reads `gitdir: <main checkout>/.git/worktrees/<name>`; the main checkout is the path before
`/.git/`.

- **Epic:** `.work/tickets/<EPIC>/epic.md`. `<EPIC>` is `E<n>`, the next unused number.
- **Task:** `.work/tickets/<EPIC>/<EPIC>-T<n>.md`. Key `<EPIC>-T<n>`.
- **Every file starts with frontmatter,** followed by the ticket body:

  ```yaml
  ---
  key: E3-T2
  title: <summary>
  status: todo        # todo | doing | review | done
  blocked_by: [E3-T1]
  labels: [agent-planned]
  ---
  ```

| Operation | How |
|---|---|
| Read one | read the file |
| List an epic's tasks | glob `.work/tickets/<EPIC>/<EPIC>-T*.md` |
| Create | write the file |
| Blocked-by edge | `blocked_by` in frontmatter |
| Update a ticket | rewrite the body below the frontmatter |
| Move status | edit `status` |
| Comment | append under a `## Log` heading: `- <yyyy-mm-dd>: <comment>` |

From any worktree, `bin/ledger.sh <KEY> status <todo|doing|review|done> "<comment>"` or
`bin/ledger.sh <KEY> comment "<text>"` does the two edits above in the main checkout's ledger
and prints `LEDGER OK <KEY> <status>`; a missing ticket exits 1 with `LEDGER FAIL <KEY>: no ticket at <path>`.
