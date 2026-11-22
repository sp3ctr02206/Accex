// Accex pill: turns assistant events into a small set of visual states.
// Events arrive from Python via window.accex.push({kind, ...}). Text is always set with
// textContent (never innerHTML): replies can quote text from the screen.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const pill = $("pill");
  const el = {
    title: $("title"), sub: $("sub"), badge: $("badge"),
    youLine: $("youLine"), you: $("you"),
    stepLine: $("stepLine"), stepLabel: $("stepLabel"), step: $("step"), bar: $("bar"),
    replyLine: $("replyLine"), reply: $("reply"),
  };

  const SCAM_PREFIX = "Stop. This looks like a scam";
  const IDLE_SUB = () => `Hold ${hotkey} to talk`;
  let hotkey = "the key";
  let steps = 0;
  let collapseTimer = null;
  let fitTimer = null;

  const STATES = {
    idle:      { title: "Accex",            sub: () => IDLE_SUB() },
    listening: { title: "Listening",        sub: () => "Speak now, release when done" },
    thinking:  { title: "Thinking",         sub: () => "Looking at your screen…" },
    speaking:  { title: "Accex",            sub: () => "Speaking" },
    acting:    { title: "Working on it",    sub: () => "" },
    asking:    { title: "Waiting for you",  sub: () => "Answer when you are ready" },
    done:      { title: "Done",             sub: () => "" },
    blocked:   { title: "Scam blocked",     sub: () => "Nothing was clicked or paid" },
    error:     { title: "Something went wrong", sub: () => "" },
  };

  function setState(name, sub) {
    pill.dataset.state = name;
    const s = STATES[name] || STATES.idle;
    el.title.textContent = s.title;
    el.sub.textContent = sub !== undefined ? sub : s.sub();
    clearTimeout(collapseTimer);
  }

  function show(line, on) { line.hidden = !on; }

  function expand(on) {
    pill.classList.toggle("expanded", on);
    scheduleFit();
  }

  function collapseLater(ms) {
    clearTimeout(collapseTimer);
    collapseTimer = setTimeout(() => {
      expand(false);
      setState("idle");
      setTimeout(() => { show(el.youLine, false); show(el.stepLine, false); show(el.replyLine, false); scheduleFit(); }, 450);
    }, ms);
  }

  function readingTime(text) {      // rough time to hear a reply, then linger a little
    const words = (text || "").split(/\s+/).length;
    return Math.min(20000, 3500 + words * 380);
  }

  function host(url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url || "a page"; }
  }

  function describe(type, p = {}) {
    switch (type) {
      case "open_url": return `Opening ${host(p.url)}`;
      case "open_app": return `Opening ${p.name || "an app"}`;
      case "click": return `Clicking ${p.target || "on the screen"}`;
      case "type_text": return `Typing “${p.text || ""}”`;
      case "press_key": return `Pressing ${String(p.keys || "").replace(/\+/g, " + ")}`;
      case "scroll": return `Scrolling ${p.direction || ""}`.trim();
      case "wait": return "Waiting for the page";
      case "email_reply": return "Sending your reply";
      default: return String(type || "Working").replace(/_/g, " ");
    }
  }

  const handlers = {
    hello(ev) {
      hotkey = ev.hotkey || hotkey;
      el.badge.hidden = ev.profile !== "senior";
      setState("idle");
      scheduleFit();
    },
    stop() { /* key down or barge-in: the following cue says which */ },
    cue(ev) {
      if (ev.name === "listening") {
        steps = 0;
        show(el.stepLine, false); show(el.replyLine, false); show(el.youLine, false);
        setState("listening");
        expand(false);
      } else if (ev.name === "thinking") {
        setState("thinking");
      } else if (ev.name === "error" && pill.dataset.state !== "blocked") {
        setState("error");
      }
    },
    transcript(ev) {
      if (!ev.text) return;
      el.you.textContent = `“${ev.text}”`;
      show(el.youLine, true);
      setState("thinking");
      expand(true);
    },
    say(ev) {
      const text = ev.text || "";
      el.reply.textContent = text;
      show(el.replyLine, true);
      expand(true);
      if (text.startsWith(SCAM_PREFIX)) setState("blocked");
      else if (text.trim().endsWith("?")) setState("asking");
      else if (pill.dataset.state !== "acting") setState("speaking");
      // while acting, the subtitle keeps showing the current step
      if (!["asking"].includes(pill.dataset.state)) collapseLater(readingTime(text));
    },
    action(ev) {
      steps += 1;
      el.stepLabel.textContent = `Step ${steps}`;
      el.step.textContent = describe(ev.type, ev.params || {});
      el.bar.style.width = `${Math.min(92, 22 + steps * 14)}%`;
      show(el.stepLine, true);
      setState("acting", describe(ev.type, ev.params || {}));
      expand(true);
    },
    action_result(ev) {
      if (!ev.ok) setState("error", ev.message || "That step didn't work");
    },
    task_end(ev) {
      if (ev.reason === "done" && steps > 0) {
        el.bar.style.width = "100%";
        if (pill.dataset.state === "acting") setState("done");
      } else if (ev.reason === "confirm") {
        setState("asking", "Say yes or no");
      } else if (ev.reason === "interrupted") {
        setState("listening");
      }
    },
    confirm(ev) {
      el.you.textContent = `“${ev.reply || ""}”`;
      show(el.youLine, true);
      setState(ev.verdict === "yes" ? "acting" : ev.verdict === "no" ? "done" : "asking");
    },
    error(ev) {
      if (pill.dataset.state === "blocked") return;
      setState("error", ev.where === "startup" ? (ev.detail || "Accex could not start") : "");
      expand(true);
      collapseLater(8000);
    },
  };

  // Ask Python to resize the window to the pill (plus room for its shadow).
  function scheduleFit() {
    clearTimeout(fitTimer);
    fitTimer = setTimeout(() => requestAnimationFrame(fit), 0);
  }

  // The window is cut to the pill's shape, so its size must match the pill exactly.
  function fit() {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.fit) return;
    const r = pill.getBoundingClientRect();
    const radius = parseFloat(getComputedStyle(pill).borderTopLeftRadius) || 30;
    api.fit(Math.ceil(r.width), Math.ceil(r.height), radius);
  }

  window.accex = {
    push(ev) {
      const fn = handlers[ev && ev.kind];
      if (fn) { try { fn(ev); } catch (e) { console.error(e); } }
    },
    _setState: setState,   // for the preview script
  };

  window.addEventListener("pywebviewready", scheduleFit);
  setState("idle");
})();
