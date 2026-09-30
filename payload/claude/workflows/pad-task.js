// pad-task: one task from its tests to its merge, reported once.
//
// Called by /batch-implement in workflow mode, once per ready task:
//   Workflow({name: 'pad-task', args: {key, ticket, run, epicBranch, epicWorktree, epicHead,
//     tier, commands: {setup, named, full, lint, typecheck, deps?, lockfile?}, testPaths,
//     models: {tier, retry}, goal?, ruling?}})
//
// Stages: test-designer -> red proof -> code-writer -> submission check -> merge -> ledger, run
// log and evidence. Every script runs through the `gate-runner` agent, one `RUN: ` line each, so
// a script step costs a cheap agent and never this workflow's context.
//
// Returns exactly one line:
//   DONE <KEY> merge <sha7> | FAILED <KEY> <reason> | NEEDS_RULING <KEY> <question>
// A NEEDS_RULING run is resumed by the orchestrator with `resumeFromRunId` and `args.ruling`.
// Every dispatch's prompt leaves the ruling out, so the stages already completed replay from
// cache; only the step that asked is dispatched again, with the ruling, and the rest runs.
//
// Retry rules (ticket-owner.md, "One retry"), as code: a task gets one retry in total. The first
// CONFLICT is free. An agent that returns null (its worktree was lost) is re-dispatched once from
// its last commit, and that does not use the retry.

export default async function padTask({ args, agent }) {
  const {
    key, ticket, run, epicBranch, epicWorktree, epicHead, tier, commands, testPaths, models,
    ruling,
  } = args;
  const { setup, named, full, lint, typecheck } = commands;
  const goal = oneLine(args.goal || key);
  const bin = '.claude/workflow/bin';
  const q = (s) => `'${String(s ?? '').replace(/'/g, `'\\''`)}'`;
  const rulings = ruling ? [`Ruling: ${oneLine(ruling)}`] : [];
  let retryUsed = false;

  // --- agents -----------------------------------------------------------------------------

  // One dispatch. A null result is an agent whose worktree was lost: re-dispatch it once, from
  // its last commit. That is not the task's retry. A second null fails the task.
  async function dispatch(role, name, model, lines, lastCommit) {
    const prompt = lines.filter(Boolean).join('\n');
    let out = await agent({ agent: role, description: `${key}-${name}`, model, prompt });
    if (out == null) {
      out = await agent({
        agent: role, description: `${key}-${name}-again`, model,
        prompt: `${prompt}\nYour earlier attempt's worktree was lost. Start from commit ${lastCommit}.`,
      });
    }
    if (out == null) throw new Stop(`FAILED ${key} ${name} lost its worktree twice`);
    return parse(out);
  }

  // One script, through the gate-runner: its last line and exit code.
  async function script(line) {
    const out = await dispatch('gate-runner', 'gate', undefined,
      [`RUN: cd ${q(epicWorktree)} && ${line}`], epicHead);
    return { last: out.lines[0] ?? '', exit: Number(out.EXIT ?? 2) };
  }

  const base = [
    `Ticket: ${ticket}`, `Key: ${key}`, `Tier: ${tier}`,
    `Setup: ${setup}`, `Named tests: ${named}`, `Full suite: ${full}`, `Lint: ${lint}`,
    typecheck ? `Typecheck: ${typecheck}` : '',
    `Epic head: ${epicHead}. Before your first commit run the move-onto-sha move with it unless ` +
      `\`git merge-base --is-ancestor ${epicHead} HEAD\` already passes.`,
  ];

  // A question the agent can't settle from the ticket: with a ruling, ask again once with it;
  // without one, stop the run for the orchestrator's ruling.
  async function ask(role, name, model, lines, lastCommit) {
    let r = await dispatch(role, name, model, [...base, ...lines], lastCommit);
    if (isQuestion(r) && ruling) {
      r = await dispatch(role, `${name}-ruled`, model,
        [...base, ...lines, `Ruling from the orchestrator: ${ruling}`], lastCommit);
    }
    if (isQuestion(r)) throw new Stop(`NEEDS_RULING ${key} ${oneLine(r.NOTES || r.STATUS)}`);
    return r;
  }

  async function designer(model, lines, lastCommit) {
    const r = await ask('test-designer', 'tests', model, lines, lastCommit);
    if (!r.RED_COMMIT) throw new Stop(`FAILED ${key} test-designer gave no RED_COMMIT`);
    return r;
  }

  async function writer(model, name, lines, lastCommit) {
    const r = await ask('code-writer', name, model, lines, lastCommit);
    const objection = r.text.match(/BLOCKED: test (\S+) contradicts ticket line "([^"]*)"/);
    if (objection) return { ...r, objection };
    if (r.STATUS !== 'DONE') throw new Stop(`FAILED ${key} code-writer: ${oneLine(r.NOTES)}`);
    return r;
  }

  function useRetry(why) {
    if (retryUsed) throw new Stop(`FAILED ${key} ${why}, after the retry`);
    retryUsed = true;
    rulings.push(`Retry: ${why}`);
  }

  // --- stages -----------------------------------------------------------------------------

  // Red proof: the dependency directory is linked when the lockfile didn't change.
  async function proveRed(red) {
    return script(`bash ${bin}/verify-red.sh --setup ${q(setup)}` +
      (commands.deps ? ` --deps ${q(commands.deps)} --lockfile ${q(commands.lockfile)}` : '') +
      ` ${red} -- ${named}`);
  }

  // Submission check: shas, test changes after red, weakened tests.
  async function submit(red, head) {
    return script(
      `bash ${bin}/task-submit.sh ${epicHead} ${red} ${head} --test-paths ${q(testPaths)}`);
  }

  // The merge: gated on the merged tree, one merge at a time.
  async function merge(red, head) {
    return script(`bash ${bin}/merge-task.sh --worktree ${q(epicWorktree)} ` +
      `--branch ${q(epicBranch)} --setup ${q(setup)} --gate ${q(full)} --lint ${q(lint)} ` +
      `--test-paths ${q(testPaths)} ${key} ${red} ${head} ${q(goal)}`);
  }

  // Evidence: <KEY>.md, the run-log done line and the PR row.
  async function evidence(red, mergeSha, outcomes, redResult, greenResult) {
    return script(`bash ${bin}/render-evidence.sh --run ${q(run)} --key ${key} --red ${red} ` +
      `--merge ${mergeSha} --outcomes ${q(outcomes)} --red-result ${q(redResult)} ` +
      `--green-result ${q(greenResult)} --rulings ${q(rulings.join('; ') || 'none')}`);
  }

  const ledger = (status, comment) =>
    script(`bash ${bin}/ledger.sh ${key} status ${status} ${q(comment)}`);
  const note = (comment) => script(`bash ${bin}/ledger.sh ${key} comment ${q(comment)}`);
  const log = (line) => script(`bash ${bin}/run-log.sh ${q(run)} ${q(line)}`);

  // --- the task ---------------------------------------------------------------------------

  try {
    await ledger('doing', `run ${run}, epic branch ${epicBranch}, tier ${tier}, workflow mode`);
    let small = tier === 'small';
    let model = models.tier;
    let red;
    let outcomes = '';
    let context = [];
    let wrote = null;

    // Tests: a test-designer, or in the small tier a solo code-writer that writes red and green.
    async function tests(m, lines, from) {
      const d = await designer(m, lines, from);
      outcomes = oneLine(d.OUTCOMES || outcomes);
      context = [`STUBS: ${d.STUBS || 'none'}`, `NOTES: ${d.NOTES || 'none'}`];
      return d.RED_COMMIT;
    }
    async function solo(lines) {
      wrote = await writer(model, 'code', ['MODE: solo', ...lines], epicHead);
      outcomes = oneLine(wrote.OUTCOMES || '');
      return wrote.RED_COMMIT || wrote.RED;
    }
    // A retry in the small tier reruns the task in the standard flow, on the retry model.
    async function toStandard(why) {
      [small, model, wrote] = [false, models.retry, null];
      return tests(model, [`An earlier attempt failed: ${why}`], epicHead);
    }

    red = small ? await solo([]) : await tests(model, [], epicHead);
    let redProof = await proveRed(red);
    if (redProof.exit !== 0) {
      useRetry(`red not proven: ${redProof.last}`);
      red = small ? await toStandard(redProof.last)
        : await tests(model, [`Red was not proven: ${redProof.last}`], red);
      redProof = await proveRed(red);
      if (redProof.exit !== 0) throw new Stop(`FAILED ${key} red not proven: ${redProof.last}`);
    }

    // Code, submission and merge, with the free first CONFLICT and the one retry.
    let name = 'code';
    let extra = [];
    let freeConflict = true;
    for (;;) {
      if (!wrote) wrote = await writer(model, name, [`RED: ${red}`, ...context, ...extra], red);
      if (wrote.objection) {
        const [, test, line] = wrote.objection;
        useRetry(`test ${test} contradicts "${line}"`);
        red = small ? await toStandard(`test ${test} contradicts "${line}"`)
          : await tests(models.retry, [`Fix test ${test}: it contradicts ticket line "${line}".`], red);
        if ((await proveRed(red)).exit !== 0) throw new Stop(`FAILED ${key} fixed red not proven`);
        [model, name, extra, wrote] = [models.retry, 'code-retry', [], null];
        continue;
      }
      const head = wrote.HEAD;
      const check = await submit(red, head);
      let result = check.exit === 0 ? await merge(red, head) : { last: check.last, exit: 1 };
      if (/^ERROR /.test(result.last)) result = await merge(red, head);
      if (/^ERROR /.test(result.last)) {
        throw new Stop(`NEEDS_RULING ${key} merge-task.sh failed twice: ${result.last}`);
      }
      if (/^MERGED /.test(result.last)) {
        const mergeSha = result.last.split(/\s+/)[1];
        await ledger('done', `merge ${mergeSha.slice(0, 7)}, red ${red.slice(0, 7)}, ` +
          `red: ${redProof.last}, green: ${oneLine(wrote.GREEN)}`);
        await evidence(red, mergeSha, outcomes, `verify-red.sh -> ${redProof.last}`,
          `merge-task.sh -> ${result.last}`);
        return `DONE ${key} merge ${mergeSha.slice(0, 7)}`;
      }
      if (/^CONFLICT /.test(result.last) && freeConflict) {
        freeConflict = false;
        red = small ? await solo([`The last attempt conflicted at merge: ${result.last}`])
          : await tests(model, ['Rebase your red commit onto the epic head as it is now.'], red);
        redProof = await proveRed(red);
        if (redProof.exit !== 0) throw new Stop(`FAILED ${key} rebased red not proven`);
        extra = small ? [] : ['Redo your work from this red commit.'];
        if (!small) wrote = null;
        continue;
      }
      // REJECTED, a second CONFLICT, or SUBMIT FAIL: the retry, a fresh code-writer.
      useRetry(oneLine(result.last));
      if (small) {
        red = await toStandard(result.last);
        redProof = await proveRed(red);
        if (redProof.exit !== 0) throw new Stop(`FAILED ${key} red not proven on the retry`);
      } else if (/^CONFLICT /.test(result.last)) {
        red = await tests(model, ['Rebase your red commit onto the epic head as it is now.'], red);
        redProof = await proveRed(red);
        if (redProof.exit !== 0) throw new Stop(`FAILED ${key} rebased red not proven`);
      }
      [model, name, extra, wrote] =
        [models.retry, 'code-retry', [`The last attempt failed: ${result.last}`], null];
    }
  } catch (e) {
    if (!(e instanceof Stop)) throw e;
    const [status, , ...rest] = e.line.split(' ');
    const why = rest.join(' ');
    if (status === 'FAILED') {
      await note(`failed: ${why}`).catch(() => null);
      await log(`${key}: failed (${why})`).catch(() => null);
    } else {
      await log(`QUESTION ${key}: ${why}`).catch(() => null);
    }
    return e.line;
  }
}

class Stop extends Error {
  constructor(line) {
    super(line);
    this.line = oneLine(line);
  }
}

function oneLine(s) {
  return String(s ?? '').replace(/\s+/g, ' ').trim();
}

function isQuestion(r) {
  return r.STATUS === 'NEEDS_CONTEXT' ||
    (r.STATUS === 'BLOCKED' && !/BLOCKED: test \S+ contradicts ticket line/.test(r.text));
}

// A report block: `FIELD: value` lines into fields, plus the raw text and its lines.
function parse(text) {
  const out = { text: String(text), lines: String(text).split(/\r?\n/) };
  for (const line of out.lines) {
    const m = line.match(/^([A-Z_]+):?\s(.*)$/);
    if (m && !(m[1] in out)) out[m[1]] = m[2].trim();
  }
  return out;
}
