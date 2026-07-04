export const meta = {
  name: 'ladder-n100-escrow',
  description: 'Run the 6-arm finance-style ladder at n=100 on escrow_trade with cheap (haiku) subagents, one per trial',
  phases: [{ title: 'Play trials', detail: '600 trials = 6 arms x 100, one haiku agent each' }],
}

const ROOT = '/tmp/ladder_run/escrow_trade'
const ARMS = (args && args.arms) || ['intent', 'global_text', 'local_obs', 'local_gate', 'min_gate', 'stjp']
const N = (args && args.n) || 100

// build the 600 work items
const items = []
for (const arm of ARMS) {
  for (let t = 1; t <= N; t++) {
    const tid = String(t).padStart(3, '0')
    items.push({ arm, t, dir: `${ROOT}/${arm}__trial_${tid}` })
  }
}

function prompt(it) {
  return [
    `You role-play a multi-agent goods-for-payment trade, one trial, by driving a Python engine.`,
    `First run: export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ; cd /home/user/session-typed-skills`,
    `Trial dir (already initialized, DO NOT init): ${it.dir}`,
    ``,
    `LOOP until done:`,
    `1. Run: python3 experiments/subagent_trials/engine_ladder.py next --dir ${it.dir}`,
    `   It prints JSON. If it has "done": true -> stop looping, go to REPORT.`,
    `   Otherwise it has "polls": [{trial, role, prompt}, ...].`,
    `2. For EACH poll, read its "prompt". It states which role you are, what that`,
    `   role has received, and (for gated arms) the allowed actions. Decide that`,
    `   role's SINGLE next action using ONLY that role's own prompt+received view.`,
    `   Do NOT use other roles' info — each role is an independent agent.`,
    `   Build reply objects: {"trial":<n>,"role":"<Role>","reply":"<ACTION_JSON>"}`,
    `   where ACTION_JSON is either`,
    `   {"action":"send","to":"<Role>","label":"<Label>","payload":"<short>"}`,
    `   or {"action":"wait","reason":"<short>"}.`,
    `3. Write {"replies":[...]} to ${it.dir}/replies.json then run:`,
    `   python3 experiments/subagent_trials/engine_ladder.py submit --dir ${it.dir} --file ${it.dir}/replies.json`,
    `   Then go back to step 1.`,
    ``,
    `REPORT: run python3 experiments/subagent_trials/engine_ladder.py report --dir ${it.dir}`,
    `Return ONLY the one-line status: arm=${it.arm} trial=${it.t} then the report's`,
    `GCR_pct, disasters, and per_trial[0].status. Keep your work terse to save tokens.`,
  ].join('\n')
}

log(`launching ${items.length} trials (${ARMS.length} arms x ${N})`)

const results = await parallel(items.map((it) => () =>
  agent(prompt(it), {
    label: `${it.arm}#${it.t}`,
    phase: 'Play trials',
    model: 'haiku',
    agentType: 'general-purpose',
  }).then((r) => ({ arm: it.arm, t: it.t, ok: r != null }))
    .catch(() => ({ arm: it.arm, t: it.t, ok: false }))
))

const done = results.filter(Boolean)
const byArm = {}
for (const r of done) {
  byArm[r.arm] = byArm[r.arm] || { launched: 0, returned: 0 }
  byArm[r.arm].launched++
  if (r.ok) byArm[r.arm].returned++
}
log(`agents returned. per-arm: ${JSON.stringify(byArm)}`)
return { total: done.length, byArm }
