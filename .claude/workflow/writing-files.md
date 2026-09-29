# Writing files

Read before writing a file whose content is prose. This is about which tool does the writing,
not about what goes in the file.

The skills here write documents: `/spec` writes the spec, `/tickets` writes the plan,
`/knowledge-layer` writes `CONTEXT.md` and `project.md`, `/batch-implement` writes the
development record. Each is English with apostrophes, backticks and tables in it, at a size
where a shell heredoc stops being reliable.

## The rule

Use `Write` or `Edit` — not a heredoc, not `sed` — when the content is any of:

- **(a)** longer than a screen or two,
- **(b)** literal prose or markdown, rather than text a script is generating, or
- **(c)** carrying `'`, `"`, `` ` ``, `$`, `|` or any other shell metacharacter.

Bash is for reading, searching, running gates and git. Where a harness tells you to prefer the
shell for file changes, this is the exception it means: "Bash genuinely cannot" is the wrong
test, because a heredoc *can* write a plan file, right up until it doesn't.

| Job | Tool |
|---|---|
| Read, search, list, run gates, git | Bash |
| One-line edit, no metacharacters in the replacement | `sed -i` is fine |
| Replacement contains prose, punctuation or non-ASCII | `Edit`, or the escape hatch below |
| A new file over ~50 lines | `Write` |
| Any spec, plan, ticket body or decision record | `Write` |

## Why a content test and not a size limit

When a quoted heredoc ends early, bash parses the remaining prose as shell code, and the first
apostrophe in it — `exercise's`, `session's`, most English — opens a quote that never closes:

```
bash: -c: line 145: unexpected EOF while looking for matching `''
bash: -c: line 147: syntax error: unexpected end of file
```

Line 145 is innocent prose. Nothing is written, so the cost is a wasted call rather than lost
work, but the error names neither the real line nor the real cause. An *unterminated* heredoc
fails differently — bash warns `here-document … delimited by end-of-file` and still runs — so
"the terminator went missing" is not the diagnosis either.

There is no threshold to quote. The same ticket text passed through a quoted heredoc at 2.6 KB
and failed at ~11 KB; a 7.4 KB command string was verified to arrive intact; the same content
written to a script file and run with `bash script.sh` works at 19 KB. Criterion (c) catches
the real failures without needing a number that isn't in evidence.

## Surgical edits to prose files

When only the shell will do, an interpreter heredoc is inert to bash in a way a `cat` heredoc
is not, and an exact-string replace is safer than any regex:

```sh
python - <<'PY'
import io
p = "docs/plan.md"
s = io.open(p, encoding="utf-8").read()
old, new = "…", "…"
assert old in s, "anchor not found"
io.open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
PY
```

Pass `encoding="utf-8"` explicitly, and do not echo the changed text back: on some hosts the
file is written correctly and the script then dies on `print`, which reports failure for a
write that succeeded. `CLAUDE.local.md` names the interpreter that works on this machine and
whether its stdout needs reconfiguring — `/setup-workflow` checks both.
