/* Ultrex Studio — frontend */



const VOICE_HINTS = {

  auto: "Genre auto-selects the best matching voice.",

  arnold: "Authoritative male — great for finance and wealth content.",

  brian: "Deep energetic male — great for motivation and discipline.",

  fable: "Warm storyteller male — great for history and narrative.",

};



const STORAGE_KEY = "ultrex_ui_state";

const AI_BTN_GENERATE = "Generate Script";

const AI_BTN_FORGE = "Forge Video →";



let writerData = null;

let writerLoading = false;

let aiHasOutput = false;

let publishLoading = false;

let jobId = null;

let pollTimer = null;

let scenes = [];

let isGenerating = false;

function normalizeNewlines(value) {
  if (typeof value !== "string") return "";
  return value
    .replace(/\\n/g, "\n")
    .replace(/\r\n?/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function normalizeWriterPayload(raw) {
  if (!raw || typeof raw !== "object") return {};
  let data = raw;
  if (data.content && typeof data.content === "object") data = data.content;
  const pick = (...keys) => {
    for (const k of keys) {
      const v = data[k];
      if (v != null && String(v).trim()) return String(v).trim();
    }
    return "";
  };
  const clean = (value) => normalizeNewlines(String(value || "").trim());
  const cleanSingleLine = (value) => clean(value).replace(/\n+/g, " ");
  return {
    title: cleanSingleLine(pick("title", "Title", "video_title")),
    script: clean(pick("script", "Script")),
    description: clean(pick("description", "Description")),
    tags: cleanSingleLine(pick("tags", "Tags", "seo_tags")),
    ig_caption: clean(pick("ig_caption", "igCaption", "instagram_caption")),
  };
}

function mergeWriterData(prev, next) {
  const n = normalizeWriterPayload(next);
  const p = prev ? normalizeWriterPayload(prev) : {};
  return {
    title: n.title || p.title || "",
    script: n.script || p.script || "",
    description: n.description || p.description || "",
    tags: n.tags || p.tags || "",
    ig_caption: n.ig_caption || p.ig_caption || "",
  };
}

// ── Boot helpers ─────────────────────────────────────────────────────────────



function $(id) {

  return document.getElementById(id);

}



function apiUrl() {

  return $("apiUrl").value.replace(/\/$/, "");

}



function updateVoiceHint() {

  const val = $("voiceSelect").value;

  $("voiceHint").textContent = VOICE_HINTS[val] || "";

}



function setApiStatus(state) {

  const dot = $("apiDot");

  const lbl = $("apiStatus");

  dot.className =

    "api-dot " +

    (state === "connected" ? "connected" : state === "error" ? "error" : "");

  lbl.textContent =

    state === "connected"

      ? "Connected"

      : state === "error"

        ? "Offline"

        : "Connecting…";

}



function getMainScript() {

  return $("scriptInput").value.trim();

}



function updateSteps() {

  const script = getMainScript();

  const hasScript = script.length > 20;

  const step1 = $("step1");

  const step2 = $("step2");

  const step3 = $("step3");



  step1.classList.toggle("done", hasScript);

  step1.classList.toggle("active", !hasScript);

  step2.classList.toggle("active", hasScript && !isGenerating);

  step2.classList.toggle("done", isGenerating || scenes.length > 0);

  step3.classList.toggle("active", isGenerating || scenes.length > 0);

}



function updateCharCount() {

  const pasteText = $("scriptInput").value;

  const writerText = $("writerScript")?.value || writerData?.script || "";

  const words = pasteText.trim() ? pasteText.trim().split(/\s+/).length : 0;

  const writerWords = writerText.trim()

    ? writerText.trim().split(/\s+/).length

    : 0;



  $("charCount").textContent = pasteText.length + " characters";

  $("wordTarget").textContent = words + " words";

  $("wordTarget").classList.remove("in-range", "over");

  if (words >= 150 && words <= 170) $("wordTarget").classList.add("in-range");

  else if (words > 170) $("wordTarget").classList.add("over");



  const wwt = $("writerWordTarget");

  if (wwt) {

    wwt.textContent = writerWords + " words";

    wwt.classList.remove("in-range", "over");

    if (writerWords >= 150 && writerWords <= 170)

      wwt.classList.add("in-range");

    else if (writerWords > 170) wwt.classList.add("over");

  }

  updateSteps();

}



// ── AI sheet ─────────────────────────────────────────────────────────────────



function lockBodyScroll(lock) {

  document.body.classList.toggle("sheet-open", lock);

}



function openAiSheet() {

  $("aiSheetOverlay").classList.add("open");

  lockBodyScroll(true);

  updateAiPrimaryBtn();

}



function closeAiSheet() {

  $("aiSheetOverlay").classList.remove("open");

  lockBodyScroll(false);

  saveState();

}



function closeAiSheetBackdrop(e) {

  if (e.target === $("aiSheetOverlay")) closeAiSheet();

}



function updateAiPrimaryBtn() {

  const btn = $("aiPrimaryBtn");

  if (!btn) return;

  const hasScript = !!$("writerScript")?.value.trim();

  aiHasOutput = hasScript || !!(writerData?.script?.trim());

  btn.textContent = aiHasOutput ? AI_BTN_FORGE : AI_BTN_GENERATE;

  btn.classList.toggle("btn-forge", aiHasOutput);

}



function onAiPrimaryClick() {

  if (aiHasOutput || $("writerScript")?.value.trim()) {

    commitAiScriptAndRender();

  } else {

    generateScript();

  }

}



async function generateScript() {

  const title = $("writerTitle").value.trim();

  if (!title) {

    toast("Enter a topic or angle for Script Forge.", "error");

    return;

  }

  if (writerLoading) return;



  writerLoading = true;

  const btn = $("aiPrimaryBtn");

  btn.innerHTML = '<span class="spinner"></span> Writing…';

  btn.disabled = true;



  try {

    const r = await fetch(apiUrl() + "/writer/generate", {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify({ title }),

    });

    if (!r.ok) throw new Error(await r.text());

    writerData = mergeWriterData(writerData, await r.json());

    applyWriterData();

    setApiStatus("connected");

    toast("Script drafted — forge when ready.", "success");

    saveState();

  } catch (e) {

    toast("Writer failed: " + e.message, "error");

    setApiStatus("error");

  } finally {

    writerLoading = false;

    btn.disabled = false;

    updateAiPrimaryBtn();

    if (!aiHasOutput) btn.textContent = AI_BTN_GENERATE;

  }

}



function applyWriterData() {
  if (!writerData) return;
  writerData = normalizeWriterPayload(writerData);

  $("writerEmpty").style.display = "none";
  $("writerOutput").classList.add("visible");
  $("generatedTitle").textContent = writerData.title || "Untitled";
  $("writerScript").value = writerData.script || "";
  if ($("metaDescription"))
    $("metaDescription").value = writerData.description || "";
  if ($("metaIg")) $("metaIg").value = writerData.ig_caption || "";
  if ($("metaTags")) $("metaTags").value = writerData.tags || "";

  updateCharCount();
  updateAiPrimaryBtn();
}

function switchMetaTab(name) {
  document.querySelectorAll(".meta-tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".meta-panel").forEach((p) => {
    p.classList.toggle("active", p.id === "meta-" + name);
  });
}

function copyMeta(fieldId) {
  const el = $(fieldId);
  if (!el?.value) return;
  navigator.clipboard
    .writeText(el.value)
    .then(() => toast("Copied to clipboard", "info"));
}



function onWriterScriptEdit() {

  if (!writerData) writerData = {};

  writerData.script = $("writerScript").value;

  updateCharCount();

  updateAiPrimaryBtn();

  saveState();

}



async function commitAiScriptAndRender() {

  const script = $("writerScript")?.value.trim();

  if (!script) {

    toast("Generate a script first.", "error");

    return;

  }

  if (isGenerating) return;



  if (!writerData) writerData = {};
  writerData = mergeWriterData(writerData, {
    script,
    title: writerData.title || $("generatedTitle")?.textContent,
    description: $("metaDescription")?.value,
    tags: $("metaTags")?.value,
    ig_caption: $("metaIg")?.value,
  });

  $("scriptInput").value = script;

  updateCharCount();

  closeAiSheet();

  saveState();

  await generate();

}



// ── Publish sheet ──────────────────────────────────────────────────────────────



function getPublishMetadata() {
  const fromWriter = writerData ? normalizeWriterPayload(writerData) : {};
  const fromMeta = {
    title: fromWriter.title,
    description: $("metaDescription")?.value?.trim() || fromWriter.description,
    tags: $("metaTags")?.value?.trim() || fromWriter.tags,
    ig_caption: $("metaIg")?.value?.trim() || fromWriter.ig_caption,
  };
  return {
    title:
      fromMeta.title ||
      (jobId ? "Ultrex — " + jobId.slice(0, 8) : ""),
    description: fromMeta.description || "",
    tags: fromMeta.tags || "",
    ig_caption: fromMeta.ig_caption || "",
  };
}

function prefillPublishFields() {
  const meta = getPublishMetadata();
  $("publishTitle").value = meta.title;
  $("publishDescription").value = meta.description;
  $("publishTags").value = meta.tags;
}



function showPublishCta() {

  const btn = $("preparePublishBtn");

  if (btn) btn.style.display = jobId ? "inline-flex" : "none";

}



function hidePublishCta() {

  const btn = $("preparePublishBtn");

  if (btn) btn.style.display = "none";

}



function showPreparePublish() {

  if (!jobId) {

    toast("Render a video first.", "error");

    return;

  }

  const videoSrc = $("finalVideo")?.src;

  if (!videoSrc) {

    toast("No video available for this job.", "error");

    return;

  }



  prefillPublishFields();

  $("publishVideo").src = videoSrc;

  $("publishSuccess").style.display = "none";

  $("publishBtn").disabled = false;

  $("publishBtn").textContent = "Publish to YouTube";

  $("publishSheetOverlay").classList.add("open");

  lockBodyScroll(true);

  saveState();

}



function closePublishSheet() {

  $("publishSheetOverlay").classList.remove("open");

  if (!$("aiSheetOverlay").classList.contains("open")) lockBodyScroll(false);

  saveState();

}



function closePublishSheetBackdrop(e) {

  if (e.target === $("publishSheetOverlay")) closePublishSheet();

}



async function publishToYouTube() {

  if (!jobId) {

    toast("No render job found.", "error");

    return;

  }

  if (publishLoading) return;



  const metadata = {

    title: $("publishTitle").value.trim(),

    description: $("publishDescription").value.trim(),

    tags: $("publishTags").value.trim(),

  };



  if (!metadata.title) {

    toast("Title is required.", "error");

    return;

  }



  publishLoading = true;

  const btn = $("publishBtn");

  btn.innerHTML = '<span class="spinner"></span> Uploading…';

  btn.disabled = true;



  try {

    const r = await fetch(apiUrl() + "/upload_to_youtube/" + jobId, {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify(metadata),

    });

    const text = await r.text();

    let data = {};

    try {

      data = text ? JSON.parse(text) : {};

    } catch {

      data = { detail: text };

    }

    if (!r.ok) {

      throw new Error(data.detail || text || "Upload failed");

    }



    if (data.youtube_url) {

      $("publishSuccess").style.display = "flex";

      $("youtubeLink").href = data.youtube_url;

      $("youtubeLink").textContent = data.youtube_url;

      toast("Published to YouTube (private).", "success");

      btn.textContent = "Published ✓";

    } else {

      toast("Upload completed.", "success");

      btn.textContent = "Published ✓";

    }

    saveState();

  } catch (e) {

    toast("Upload failed: " + e.message, "error");

    btn.innerHTML = "Publish to YouTube";

    btn.disabled = false;

  } finally {

    publishLoading = false;

  }

}



// ── Video pipeline ─────────────────────────────────────────────────────────────



async function generate() {

  const script = getMainScript();

  const niche = $("nicheSelect").value;

  const rawVoice = $("voiceSelect").value;

  const voice = rawVoice === "auto" ? null : rawVoice;



  if (!script) {

    toast("Paste your script first.", "error");

    return;

  }

  if (isGenerating) return;



  isGenerating = true;

  hidePublishCta();

  const btn = $("genBtn");

  btn.innerHTML = '<span class="spinner"></span> Launching pipeline…';

  btn.disabled = true;

  updateSteps();



  try {

    const r = await fetch(apiUrl() + "/process_scene", {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify({ script, niche, voice }),

    });



    if (!r.ok) throw new Error(await r.text());

    const data = await r.json();



    jobId = data.job_id;

    scenes = data.scenes || [];



    setApiStatus("connected");

    saveState();

    showProgress();

    renderScenes(scenes);

    startPolling();

    loadJobs();

    toast("Pipeline started — " + scenes.length + " scenes", "info");

  } catch (e) {

    isGenerating = false;

    btn.innerHTML = "Render Video";

    btn.disabled = false;

    updateSteps();

    toast("Error: " + e.message, "error");

    setApiStatus("error");

  }

}



function startPolling() {

  const interval = parseInt($("pollInterval").value, 10) || 3000;

  clearInterval(pollTimer);

  poll();

  pollTimer = setInterval(poll, interval);

}



async function poll() {

  if (!jobId) return;

  try {

    const r = await fetch(apiUrl() + "/get_status/" + jobId);

    if (!r.ok) return;

    const data = await r.json();

    scenes = data.scenes || [];

    const status = data.status;



    updateProgress(scenes, status);

    renderScenes(scenes);

    saveState();



    if (status === "compiling") {

      $("vidRow").style.display = "flex";

      setStatusPill("compiling");

    }



    if (status === "done") {

      clearInterval(pollTimer);

      isGenerating = false;

      setStatusPill("done");

      $("vidRow").style.display = "none";

      $("genBtn").innerHTML = "Render Video";

      $("genBtn").disabled = false;

      updateSteps();

      saveState();

      loadJobs();

      if (data.video_url) showVideo(data.video_url);

      showPublishCta();

      toast("Your short is ready.", "success");

      confetti();

    }



    if (status === "failed") {

      clearInterval(pollTimer);

      isGenerating = false;

      setStatusPill("failed");

      $("genBtn").innerHTML = "Render Video";

      $("genBtn").disabled = false;

      updateSteps();

      saveState();

      loadJobs();

      hidePublishCta();

      toast("Pipeline failed: " + (data.error || "unknown error"), "error");

    }

  } catch {

    /* ignore transient poll errors */

  }

}



// ── Jobs history ─────────────────────────────────────────────────────────────



async function loadJobs() {

  const list = $("jobsList");

  try {

    const r = await fetch(apiUrl() + "/jobs");

    if (!r.ok) return;

    const jobs = await r.json();

    const entries = Object.entries(jobs).slice(0, 6);

    if (!entries.length) {

      list.innerHTML = '<div class="jobs-empty">No renders yet</div>';

      return;

    }

    list.innerHTML = "";

    entries.forEach(([id, job]) => {

      const el = document.createElement("div");

      el.className = "job-item";

      el.innerHTML = `

        <span title="${id}">${(job.niche || "Video").slice(0, 12)} · ${job.scene_count || "?"} scenes</span>

        <span class="job-status ${job.status}">${job.status}</span>

      `;

      el.onclick = () => resumeJob(id, job);

      list.appendChild(el);

    });

  } catch {

    list.innerHTML =

      '<div class="jobs-empty">Connect backend to see history</div>';

  }

}



async function resumeJob(id, preview) {

  if (preview?.status === "done" && preview?.video_url) {

    jobId = id;

    showProgress();

    setStatusPill("done");

    showVideo(preview.video_url);

    showPublishCta();

    toast("Loaded completed render", "info");

    saveState();

    return;

  }

  jobId = id;

  hidePublishCta();

  showProgress();

  setStatusPill(preview?.status || "generating");

  startPolling();

  toast("Resuming job…", "info");

  saveState();

}



// ── UI helpers ───────────────────────────────────────────────────────────────



function switchTab(name) {

  document.querySelectorAll(".card-tabs .tab").forEach((t) => {

    t.classList.toggle("active", t.dataset.tab === name);

  });

  document

    .querySelectorAll(".tab-panel")

    .forEach((p) => p.classList.remove("active"));

  $("panel-" + name).classList.add("active");

}



function showProgress() {

  $("progressSection").classList.add("visible");

  $("storyboard").classList.add("visible");

}



function updateProgress(scenesList, status) {

  const total = scenesList.length;

  if (!total) return;

  const img = scenesList.filter((s) => s.image_url).length;

  const aud = scenesList.filter((s) => s.audio_url).length;

  $("imgBar").style.width = Math.round((img / total) * 100) + "%";

  $("audBar").style.width = Math.round((aud / total) * 100) + "%";

  $("imgCount").textContent = img + "/" + total;

  $("audCount").textContent = aud + "/" + total;

}



function setStatusPill(state) {

  const pill = $("statusPill");

  pill.className = "status-pill " + state;

  pill.textContent = state.charAt(0).toUpperCase() + state.slice(1);

}



function renderScenes(scenesList) {

  const grid = $("sceneGrid");

  grid.innerHTML = "";

  scenesList.forEach((scene) => {

    const allDone = scene.image_url && scene.audio_url;

    const imgDone = !!scene.image_url;

    const beat = scene.beat_tag || "setup";



    const tile = document.createElement("div");

    tile.className = "scene-tile" + (allDone ? " done" : "");

    tile.onclick = () => openModal(scene);



    tile.innerHTML = `

      <div class="scene-img-wrap">

        ${

          scene.image_url

            ? `<img src="${scene.image_url}" loading="lazy" alt="Scene ${scene.scene_number}"/>`

            : `<div class="scene-img-placeholder">

               <div class="shimmer"></div>

               <span>Rendering…</span>

             </div>`

        }

      </div>

      <div class="scene-meta">

        <span class="scene-num">#${scene.scene_number}

          <span class="beat-badge beat-${beat}">${beat}</span>

        </span>

        <div class="scene-status-dot ${allDone ? "all-done" : imgDone ? "img-done" : ""}"></div>

      </div>

      ${scene.audio_url ? `<div class="audio-mini"><audio controls src="${scene.audio_url}"></audio></div>` : ""}

    `;

    grid.appendChild(tile);

  });

}



function showVideo(url) {

  $("videoResult").classList.add("visible");

  $("finalVideo").src = url;

  $("dlBtn").href = url;

  showPublishCta();

  $("videoResult").scrollIntoView({ behavior: "smooth", block: "start" });

}



function resetAll() {

  clearInterval(pollTimer);

  isGenerating = false;

  jobId = null;

  scenes = [];

  writerData = null;

  aiHasOutput = false;

  clearState();



  $("scriptInput").value = "";

  $("writerTitle").value = "";

  $("writerScript").value = "";

  $("writerEmpty").style.display = "block";

  $("writerOutput").classList.remove("visible");
  $("metaDescription").value = "";
  $("metaIg").value = "";
  $("metaTags").value = "";

  $("publishTitle").value = "";

  $("publishDescription").value = "";

  $("publishTags").value = "";

  $("publishVideo").src = "";

  $("publishSuccess").style.display = "none";



  closeAiSheet();

  closePublishSheet();

  updateCharCount();

  updateAiPrimaryBtn();

  $("progressSection").classList.remove("visible");

  $("storyboard").classList.remove("visible");

  $("videoResult").classList.remove("visible");

  hidePublishCta();

  $("sceneGrid").innerHTML = "";

  $("finalVideo").src = "";

  $("genBtn").innerHTML = "Render Video";

  $("genBtn").disabled = false;

  $("vidRow").style.display = "none";

  setStatusPill("generating");

  $("voiceSelect").value = "auto";

  updateVoiceHint();

  updateSteps();

}



function openModal(scene) {

  $("modalTitle").textContent = "Scene " + scene.scene_number;

  $("modalScript").textContent = scene.script_segment || "—";

  $("modalPrompt").textContent = scene.ai_image_prompt || "—";

  $("modalOverlay").classList.add("open");

}



function closeModal(e) {

  if (e.target === $("modalOverlay"))

    $("modalOverlay").classList.remove("open");

}



async function pingAPI() {

  try {

    const r = await fetch(apiUrl() + "/");

    if (r.ok) {

      setApiStatus("connected");

      toast("Backend online", "success");

      loadJobs();

    } else {

      setApiStatus("error");

      toast("Backend returned " + r.status, "error");

    }

  } catch {

    setApiStatus("error");

    toast("Cannot reach backend", "error");

  }

}



function toast(msg, type = "info") {

  const el = document.createElement("div");

  el.className = "toast " + type;

  el.textContent = msg;

  $("toastContainer").appendChild(el);

  setTimeout(() => el.remove(), 4000);

}



function confetti() {

  const canvas = document.createElement("canvas");

  canvas.style.cssText =

    "position:fixed;inset:0;z-index:9999;pointer-events:none;";

  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d");

  canvas.width = innerWidth;

  canvas.height = innerHeight;

  const colors = ["#1a6ef7", "#38bdf8", "#22d3a4", "#a78bfa", "#ffffff"];

  const pieces = Array.from({ length: 100 }, () => ({

    x: Math.random() * innerWidth,

    y: Math.random() * -200,

    r: Math.random() * 5 + 3,

    color: colors[Math.floor(Math.random() * colors.length)],

    vx: (Math.random() - 0.5) * 2,

    vy: Math.random() * 4 + 2,

    angle: Math.random() * 360,

    spin: (Math.random() - 0.5) * 8,

  }));

  let frame = 0;

  function draw() {

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    pieces.forEach((p) => {

      ctx.save();

      ctx.translate(p.x, p.y);

      ctx.rotate((p.angle * Math.PI) / 180);

      ctx.fillStyle = p.color;

      ctx.globalAlpha = Math.max(0, 1 - frame / 120);

      ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);

      ctx.restore();

      p.x += p.vx;

      p.y += p.vy;

      p.angle += p.spin;

    });

    frame++;

    if (frame < 120) requestAnimationFrame(draw);

    else canvas.remove();

  }

  draw();

}



// ── Persistence ────────────────────────────────────────────────────────────────



function saveState() {

  const payload = {

    apiUrl: $("apiUrl").value,

    writerData,

    scriptInput: $("scriptInput").value,

    writerTitle: $("writerTitle").value,

    jobId,

    scenes,

    isGenerating,

    status: $("statusPill")?.textContent?.toLowerCase() || null,

    video_url: $("finalVideo")?.src || null,

    publishTitle: $("publishTitle")?.value || "",

    publishDescription: $("publishDescription")?.value || "",

    publishTags: $("publishTags")?.value || "",

    metaDescription: $("metaDescription")?.value || "",

    metaIg: $("metaIg")?.value || "",

    metaTags: $("metaTags")?.value || "",

  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));

}



function clearState() {

  localStorage.removeItem(STORAGE_KEY);

}



function restoreState() {

  const saved = localStorage.getItem(STORAGE_KEY);

  if (!saved) return;

  try {

    const p = JSON.parse(saved);

    if (p.apiUrl) $("apiUrl").value = p.apiUrl;

    if (p.scriptInput) $("scriptInput").value = p.scriptInput;

    if (p.writerTitle) $("writerTitle").value = p.writerTitle;

    if (p.writerData) {

      writerData = mergeWriterData(p.writerData, {

        description: p.metaDescription,

        tags: p.metaTags,

        ig_caption: p.metaIg,

      });

      applyWriterData();

    }

    if (p.publishTitle) $("publishTitle").value = p.publishTitle;

    if (p.publishDescription)

      $("publishDescription").value = p.publishDescription;

    if (p.publishTags) $("publishTags").value = p.publishTags;

    jobId = p.jobId || null;

    scenes = p.scenes || [];

    isGenerating = p.isGenerating || false;

    if (scenes.length) {

      showProgress();

      renderScenes(scenes);

    }

    if (p.status) setStatusPill(p.status);

    if (p.video_url && p.status === "done") {

      showVideo(p.video_url);

    }

    if (jobId && p.status && p.status !== "done" && p.status !== "failed")

      startPolling();



    updateCharCount();

    updateAiPrimaryBtn();

    updateSteps();

  } catch {

    clearState();

  }

}



// ── Init ───────────────────────────────────────────────────────────────────────



window.addEventListener("load", () => {

  $("scriptInput").addEventListener("input", () => {

    updateCharCount();

    saveState();

  });

  $("writerScript")?.addEventListener("input", onWriterScriptEdit);



  restoreState();

  updateVoiceHint();

  updateCharCount();

  updateAiPrimaryBtn();

  setTimeout(pingAPI, 600);

});



window.switchTab = switchTab;

window.pingAPI = pingAPI;

window.generate = generate;

window.onAiPrimaryClick = onAiPrimaryClick;

window.openAiSheet = openAiSheet;

window.closeAiSheet = closeAiSheet;

window.closeAiSheetBackdrop = closeAiSheetBackdrop;

window.showPreparePublish = showPreparePublish;

window.closePublishSheet = closePublishSheet;

window.closePublishSheetBackdrop = closePublishSheetBackdrop;

window.publishToYouTube = publishToYouTube;

window.resetAll = resetAll;

window.closeModal = closeModal;

window.updateVoiceHint = updateVoiceHint;
window.switchMetaTab = switchMetaTab;
window.copyMeta = copyMeta;


