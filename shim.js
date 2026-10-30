// Static-site stand-in for the DrillPad API. Lessons come from data/*.json; progress and whiteboard sessions
// live in this browser's localStorage. Scheduling is a simplified approximation of the Mac app's FSRS.
(() => {
  const KEY = "drillpad.static.v1";
  const base = new URL(".", document.currentScript.src).href;
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || { done: [], sessions: [], next: 1 }; } catch { return { done: [], sessions: [], next: 1 }; } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify(s)); return true; } catch { return false; } };
  const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });
  const getJ = (p) => fetch(base + p).then((r) => r.json());
  const DAY = 864e5;

  function state(rows, now) {
    let iv = 0, due = 0, t = 0;
    for (const r of rows) {
      t = Date.parse(r.at);
      iv = r.score <= 3 ? 1 : r.score === 4 ? Math.max(3, iv * 2.2) : Math.max(5, iv * 3.5);
      iv = Math.min(45, iv); due = t + iv * DAY;
    }
    const last = rows[rows.length - 1], recent = rows.slice(-3).map((r) => r.score);
    return { sessions: rows.length, last_score: last.score, last_at: last.at,
      recent_avg: Math.round(recent.reduce((a, b) => a + b, 0) / recent.length * 100) / 100,
      due: new Date(due).toISOString(), due_now: due <= now,
      retrievability: Math.round(Math.pow(0.9, (now - t) / DAY / iv) * 1000) / 1000 };
  }
  const forLesson = (s, m, l) => s.sessions.filter((x) => x.m === m && x.l === l).sort((a, b) => a.at < b.at ? -1 : a.at > b.at ? 1 : a.id - b.id);
  const detail = (s, m, l) => { const rows = forLesson(s, m, l);
    return { module: m, lesson: l, state: rows.length ? state(rows, Date.now()) : null,
      history: rows.map((r) => ({ id: r.id, score: r.score, notes: r.notes, at: r.at })).reverse() }; };

  async function overview(s) {
    const mods = await getJ("data/modules.json"), now = Date.now(), by = {};
    s.sessions.forEach((r) => (by[r.m + "/" + r.l] = by[r.m + "/" + r.l] || []).push(r));
    const lessons = {}, due = [];
    for (const [k, rows] of Object.entries(by)) {
      rows.sort((a, b) => a.at < b.at ? -1 : a.at > b.at ? 1 : a.id - b.id);
      const [m, l] = k.split("/"), mod = mods.find((x) => x.id === m); if (!mod) continue;
      const les = mod.lessons.find((x) => x.id === l), st = state(rows, now); lessons[k] = st;
      if (st.due_now) due.push({ module: m, lesson: l, module_title: mod.title, title: les ? les.title : l, ...st });
    }
    due.sort((a, b) => a.due < b.due ? -1 : 1);
    const vals = Object.values(lessons);
    return { lessons, due, summary: { total_lessons: mods.reduce((n, m) => n + m.lessons.length, 0), whiteboarded: vals.length, due_now: due.length,
      mean_last_score: vals.length ? Math.round(vals.reduce((a, v) => a + v.last_score, 0) / vals.length * 100) / 100 : null } };
  }

  async function modules(s) {
    const mods = await getJ("data/modules.json"), d = new Set(s.done);
    mods.forEach((m) => { let n = 0; m.lessons.forEach((l) => { l.done = d.has(m.id + "/" + l.id); n += l.done; }); m.done = n; });
    return mods;
  }
  async function curricula(s) {
    const [cs, mods] = await Promise.all([getJ("data/curricula.json"), modules(s)]), by = Object.fromEntries(mods.map((m) => [m.id, m]));
    cs.forEach((c) => { let tot = 0; c.levels.forEach((lv) => lv.units.forEach((u) => { const m = by[u.module_id]; if (m) { u.done = m.done; tot += m.done; } }));
      if (c.progress) c.progress.done = tot; });
    return cs;
  }

  // Lessons in learning order: the core curriculum's stage order, written lessons only.
  // The ramp (data/ramp.json, optional): a front-loaded order for its curriculum that comes before the course order.
  const getRamp = () => getJ("data/ramp.json").catch(() => null);
  const curSel = async () => { try { return localStorage.getItem("dp_cur"); } catch { return null; } };
  async function ordered(s, want) {
    const [cs, mods, ramp] = await Promise.all([getJ("data/curricula.json"), getJ("data/modules.json"), getRamp()]);
    const by = Object.fromEntries(mods.map((m) => [m.id, m])), done = new Set(s.done), seen = new Set(), out = [];
    const rampOn = ramp && ramp.curriculum === want, inRamp = new Set();
    if (rampOn) for (const r of ramp.lessons) {
      const [m, l] = r.key.split("/"), les = by[m] && by[m].lessons.find((x) => x.id === l);
      if (!les || !les.written) continue;
      inRamp.add(r.key);
      out.push({ module: m, lesson: l, title: les.title, module_title: by[m].title, done: done.has(r.key), focus: true, ramp: true, stage: r.stage });
    }
    ordered.ramp = rampOn ? ramp : null;
    const core = cs.find((c) => c.id === want) || cs.find((c) => c.id === "core") || cs[0];
    ordered.title = core ? core.title : "";
    const ids = core ? core.levels.flatMap((lv) => lv.units.map((u) => u.module_id)) : [], focus = new Set(ids);
    for (const id of [...ids, ...mods.map((m) => m.id)]) {
      const m = by[id]; if (!m || seen.has(id)) continue; seen.add(id);
      for (const l of m.lessons) if (l.written && !inRamp.has(m.id + "/" + l.id)) out.push({ module: m.id, lesson: l.id, title: l.title, module_title: m.title, done: done.has(m.id + "/" + l.id), focus: focus.has(m.id) });
    }
    return out;
  }
  // "Next lesson": first unfinished lesson after the one just finished, else the first unfinished anywhere.
  async function nextLesson(s, m, l) {
    const all = await ordered(s, (await curSel()) || (await getRamp() || {}).curriculum), i = all.findIndex((x) => x.module === m && x.lesson === l);
    const n = all.slice(i + 1).find((x) => !x.done) || all.find((x) => !x.done && !(x.module === m && x.lesson === l));
    return n ? { kind: "lesson", module: n.module, lesson: n.lesson, title: n.title, module_title: n.module_title, reason: "next unfinished lesson in the course order" } : { kind: "none" };
  }
  // "Today": the unfinished lessons in course order, dealt out `per` a day starting today, one row per calendar date.
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  async function today(s, per, cur) {
    const todo = (await ordered(s, cur)).filter((x) => !x.done), now = new Date();
    if (!s.start) { s.start = ymd(now); save(s); }
    const ramp = ordered.ramp, schedule = [];
    for (let i = 0, d = 0; i < todo.length; i += per, d++) {
      const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() + d), lessons = todo.slice(i, i + per), r = lessons.find((x) => x.ramp);
      schedule.push({ date: ymd(day), lessons, whiteboard: r ? ramp.stages[r.stage].whiteboard : null });
    }
    const lastFocus = todo.map((x) => x.focus).lastIndexOf(true), focusDay = schedule.length && lastFocus >= 0 ? schedule[Math.floor(lastFocus / per)].date : null;
    const lastRamp = todo.map((x) => x.ramp).lastIndexOf(true), rampEnd = schedule.length && lastRamp >= 0 ? schedule[Math.floor(lastRamp / per)].date : null;
    return { storageOk: save(s), doneCount: s.done.length, start: s.start, curriculum: ordered.title, focusEnd: focusDay, rampEnd, per, remaining: todo.length, schedule, due: (await overview(s)).due };
  }

  const real = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.includes("/api/")) return real(input, init);
    const p = url.pathname.slice(url.pathname.indexOf("/api/") + 5).split("/"), method = (init.method || "GET").toUpperCase(), s = load();
    try {
      if (p[0] === "modules" && p.length === 1) return json(await modules(s));
      if (p[0] === "curricula") return json(await curricula(s));
      if (p[0] === "next") return json(await nextLesson(s, url.searchParams.get("module"), url.searchParams.get("lesson")));
      if (p[0] === "today") { const rp = await getRamp(); return json(await today(s, Math.max(1, Math.min(6, +url.searchParams.get("per") || (rp && rp.curriculum === url.searchParams.get("c") && rp.per) || 3)), url.searchParams.get("c"))); }
      if (p[0] === "start" && method === "POST") { s.start = JSON.parse(init.body).start; save(s); return json({ start: s.start }); }
      if (p[0] === "modules" && p.length === 3 && p[2] !== "done") return json(await getJ(`data/lessons/${p[1]}__${p[2]}.json`));
      if (p[0] === "modules" && p[3] === "done") {
        const k = p[1] + "/" + p[2], on = url.searchParams.get("done") !== "false";
        s.done = s.done.filter((x) => x !== k); if (on) s.done.push(k); return json({ done: on, saved: save(s) });
      }
      if (p[0] === "whiteboard") {
        if (p.length === 1) return json(await overview(s));
        if (p[1] === "sessions" && method === "DELETE") {
          const row = s.sessions.find((x) => x.id === +p[2]); if (!row) return json({ detail: "unknown session" }, 404);
          s.sessions = s.sessions.filter((x) => x.id !== row.id); save(s); return json(detail(s, row.m, row.l));
        }
        if (method === "POST") {
          const b = JSON.parse(init.body), now = new Date(), when = b.at ? new Date(b.at) : now;
          if (isNaN(when) || when > now.getTime() + 3e5) return json({ detail: "at cannot be in the future" }, 422);
          s.sessions.push({ id: s.next++, m: p[1], l: p[2], score: b.score, notes: (b.notes || "").trim(), at: when.toISOString() });
          save(s); return json(detail(s, p[1], p[2]));
        }
        return json(detail(s, p[1], p[2]));
      }
    } catch (e) { return json({ detail: String(e) }, 500); }
    return json({ detail: "not available in the static site" }, 404);
  };
})();
