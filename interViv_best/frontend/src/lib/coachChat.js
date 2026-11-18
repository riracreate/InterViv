export const EXPLAIN_24H_NOTE =
  'Viewing this explanation counts as teaching exposure. A new attempt on the same item within 24 hours will be marked as practised with help, not independent assessment.';

const CHIP_TYPES = new Set(['create_plan', 'start_task', 'assess_independently', 'update_hours']);

export function buildSuggestionChips(reply, hasPlan) {
  const chips = [];
  for (const action of reply?.actions || []) {
    if (action && CHIP_TYPES.has(action.type)) {
      chips.push({ type: action.type, label: action.label || action.type, action });
    }
  }
  if (hasPlan) chips.push({ type: 'why_this_task', label: 'Why this task?', text: 'Why this task?' });
  return chips;
}

export function toolCardView(proposal) {
  if (!proposal || typeof proposal !== 'object') return null;
  const args = proposal.args || {};
  if (proposal.tool === 'update_plan') {
    return {
      tool: proposal.tool,
      title: 'Update your study plan?',
      lines: [
        `Goal: ${args.goal || 'your saved goal'}`,
        `Hours per week: ${args.hours_per_week ?? 'your saved hours'}`,
        `Skills: ${(args.skills || []).join(', ') || 'your saved skills'}`,
      ],
      note: null,
      confirmLabel: 'Confirm plan update',
    };
  }
  if (proposal.tool === 'start_practice') {
    return {
      tool: proposal.tool,
      title: 'Start practice?',
      lines: [
        `Skills: ${(args.skills || []).join(', ')}`,
        `Mode: ${args.practice_mode || 'coached_practice'}`,
        `Flow: ${args.flow_preset || 'legacy'}`,
      ],
      note: null,
      confirmLabel: 'Confirm and start',
    };
  }
  if (proposal.tool === 'explain_last_interview') {
    return {
      tool: proposal.tool,
      title: 'Explain your last interview?',
      lines: [`Session: ${args.session_id || 'your last completed session'}`],
      note: EXPLAIN_24H_NOTE,
      confirmLabel: 'Confirm explanation',
    };
  }
  return null;
}

export function confirmRequest(proposal) {
  const view = toolCardView(proposal);
  if (!view) return null;
  return { tool: view.tool, args: proposal.args || {} };
}

export function dismissRequest() {
  return null;
}

export function parseSseText(text) {
  const events = [];
  for (const block of String(text || '').split('\n\n')) {
    if (!block.trim()) continue;
    let event = 'message';
    const dataLines = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }
    let data = dataLines.join('\n');
    try {
      data = JSON.parse(data);
    } catch {
      // Keep raw text data as-is.
    }
    events.push({ event, data });
  }
  return events;
}

export function assembleStream(events) {
  let text = '';
  let toolProposal = null;
  let done = null;
  for (const item of events || []) {
    if (item.event === 'token') text += item.data?.text || '';
    if (item.event === 'tool_proposal') toolProposal = item.data;
    if (item.event === 'done') done = item.data;
  }
  return { text, toolProposal, done };
}
