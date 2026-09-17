// Perchlings shop site. Two things to fill in before launch, nothing else needs touching:
const CONFIG = {
  buyUrl: "",                 // the checkout link from the payment provider (Lemon Squeezy, Gumroad, ...). Empty = the demo checkout below.
  contact: "",                // an email address for the footer. Empty = no contact link.
  demoAdopt: true,            // TEMPORARY: Adopt buttons open adopt.html, a pretend checkout with no payment. Set false once buyUrl is set.
};

(() => {
  // --- buy buttons and contact
  for (const a of document.querySelectorAll("[data-buy]")) {
    if (CONFIG.buyUrl) { a.href = CONFIG.buyUrl; a.rel = "noopener"; }
    else if (CONFIG.demoAdopt) { a.href = "adopt.html"; }
    else { a.textContent = "Adoptions open soon"; a.href = "#price"; }
  }
  for (const a of document.querySelectorAll("[data-item]")) {                 // shop items: the real store once it exists, the demo checkout until then
    if (CONFIG.buyUrl) { a.href = CONFIG.buyUrl; a.rel = "noopener"; }
  }
  const slot = document.getElementById("contact-slot");
  if (slot && CONFIG.contact) {
    const a = document.createElement("a"); a.href = "mailto:" + CONFIG.contact; a.textContent = "Write to us"; slot.append(" · ", a);
  }

  // --- the bar that follows you once the first Adopt button has scrolled away
  const bar = document.getElementById("buybar"), heroBtn = document.getElementById("hero-buy");
  if (bar && heroBtn && "IntersectionObserver" in window) {
    new IntersectionObserver((es) => {
      const on = !es[0].isIntersecting && es[0].boundingClientRect.top < 0;
      bar.classList.toggle("on", on); bar.setAttribute("aria-hidden", on ? "false" : "true"); bar.toggleAttribute("inert", !on);
    }).observe(heroBtn);
  }

  // --- clips only play while they're on screen; if the MP4 can't play, the GIF inside takes its place
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const vids = document.querySelectorAll("video[autoplay]");
  const toGif = (v) => { const img = v.querySelector("img"); if (img && v.parentNode) { img.loading = "lazy"; v.replaceWith(img); } };
  for (const v of vids) {
    const last = v.querySelector("source:last-of-type");
    if (last) last.addEventListener("error", () => toGif(v));
    v.addEventListener("error", () => toGif(v));
    if (reduce) { v.removeAttribute("autoplay"); v.controls = true; }
  }
  if (vids.length && !reduce && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => {
      for (const e of es) { const v = e.target; if (e.isIntersecting) v.play().catch(() => {}); else v.pause(); }
    }, { rootMargin: "120px" });
    vids.forEach((v) => io.observe(v));
  }

  // --- the taskbar clock under the live pets
  const clock = document.getElementById("clock");
  if (clock) {
    const tick = () => { const d = new Date(); clock.textContent = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); };
    tick(); setInterval(tick, 20000);
  }

  // --- the hero: four pets, live. They blink, breathe, watch the cursor, say their lines; click one to try a hat on it.
  const box = document.getElementById("stage"), canvas = document.getElementById("c"), hero = document.getElementById("hero");
  if (!box || !canvas || !hero) return;                     // the other pages share this file and have no stage
  const P = window.Perchlings;
  let renderer;
  try {
    if (!window.THREE || !P) throw new Error("no three");
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (e) {
    hero.classList.add("no-webgl");                          // no WebGL: the dance clip stands in for the live pets
    const v = document.createElement("video"); v.muted = true; v.loop = true; v.autoplay = !reduce; v.playsInline = true; v.controls = reduce;
    v.setAttribute("aria-label", "The four pets dancing in step on the taskbar"); v.poster = "img/hero-poster.jpg";
    const src = document.createElement("source"); src.src = "img/hero.mp4"; src.type = "video/mp4"; v.appendChild(src);
    const img = document.createElement("img"); img.src = "img/hero.gif"; img.alt = "The four pets dancing in step on the taskbar"; v.appendChild(img);
    box.appendChild(v); return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  P.setupRenderer(THREE, renderer);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 40);
  P.addLights(THREE, scene);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.35 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.74; ground.receiveShadow = true; scene.add(ground);

  // the pets' real lines, from their character files
  const LINES = {
    antenna: ["Hi. Did you hear that?", "Hi. I heard everything.", "You were gone a while. I counted.", "I have news. Come here.", "Psst. Anything new?"],
    ears: ["Hi. Look at me.", "I've been waiting.", "You left. I fainted. Twice.", "Hello? Star here.", "You're obsessed with me. Fair."],
    leaf: ["Oh. Hey.", "Five more minutes.", "You're back. I didn't move.", "Play with me? Or don't.", "Borrowing this. Forever."],
    horns: ["Sup.", "The legend is here.", "Took you long enough.", "Mine now. Cry about it.", "Play with me. It's an order."],
  };
  const START = { antenna: "happy", ears: "happy", leaf: "sleepy", horns: "sulky" };
  const HATS = [""].concat(["cap", "beanie", "party"].filter((h) => P.HATS[h]));   // the hats that come with every pet, nothing that costs extra
  const lineup = new THREE.Group(); scene.add(lineup);
  const pets = P.SPECIES.map((sp, i) => {
    const g = P.makePet(THREE, sp); P.setMood(g, START[sp.id] || "happy");
    g.userData.index = i; g.userData.sp = sp; g.userData.hat = 0; g.userData.hop = 0; g.userData.line = 0;
    g.userData.blinkAt = 2 + Math.random() * 3; g.userData.phase = Math.random() * Math.PI * 2; g.userData.pose = "idle"; g.userData.poseUntil = 0;
    lineup.add(g); return g;
  });
  const bubbles = pets.map((g) => {
    const b = document.createElement("div"); b.className = "bub"; b.setAttribute("aria-hidden", "true"); box.appendChild(b); return b;
  });

  function nextHat(g) {
    g.userData.hat = (g.userData.hat + 1) % HATS.length;
    P.wear(THREE, g, g.userData.sp, HATS[g.userData.hat]);
    P.setMood(g, g.userData.hat ? "happy" : "surprised");
    g.userData.hop = 1;
    if (hatsOff) hatsOff.hidden = false;
  }
  const hatsOff = document.getElementById("hats-off");
  if (hatsOff) hatsOff.addEventListener("click", () => {
    for (const g of pets) { g.userData.hat = 0; P.wear(THREE, g, g.userData.sp, ""); P.setMood(g, START[g.userData.sp.id] || "happy"); }
    hatsOff.hidden = true;
  });

  // a pet speaks: the bubble sits over its head, it hops, and it waves for a moment
  let talkAt = 1.8, talker = -1;
  function speak(i, text, t) {
    const g = pets[i], b = bubbles[i];
    b.textContent = text || LINES[g.userData.sp.id][g.userData.line++ % LINES[g.userData.sp.id].length];
    b.classList.add("on"); g.userData.hop = Math.max(g.userData.hop, 0.6);
    if (g.userData.mood === "sleepy") { P.setMood(g, "happy"); g.userData.mood = "happy"; }
    g.userData.pose = "wave1"; g.userData.poseUntil = t + 1.1; P.setPose(g, "wave1");
    g.userData.talkUntil = t + 2.8;
  }

  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), pointer = new THREE.Vector2(0, 0);
  function toNdc(e) {
    const r = canvas.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * 2 - 1, -(((e.clientY - r.top) / r.height) * 2 - 1)];
  }
  window.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    // the pets watch the cursor anywhere on the page, not just over the stage
    pointer.x = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1));
    pointer.y = Math.max(-1, Math.min(1, -(((e.clientY - (r.top + r.height / 2)) / (r.height * 2)) * 2)));
  }, { passive: true });
  canvas.addEventListener("pointerup", (e) => {
    const [x, y] = toNdc(e); ndc.set(x, y);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(lineup.children, true)[0];
    if (hit) { let o = hit.object; while (o && o.userData.index === undefined) o = o.parent; if (o) { nextHat(o); speak(o.userData.index, null, clock3.getElapsedTime()); } }
  });

  function resize() {
    const w = box.clientWidth, h = box.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const narrow = w < 640;
    const gap = narrow ? 1.35 : 1.9;
    pets.forEach((g, i) => { g.position.x = (i - 1.5) * gap; });
    // the feet sit just above the taskbar strip at the bottom of the box
    camera.position.set(0, narrow ? 1.0 : 0.8, narrow ? 8.6 : 7.2); camera.lookAt(0, -0.05, 0); camera.updateMatrixWorld();
    // the feet (world y -0.74) land on the top edge of the taskbar strip: shift the lineup by the difference
    lineup.position.y = 0;
    const feet = new THREE.Vector3(0, -0.74, 0).project(camera);
    const feetPx = (1 - feet.y) / 2 * h, wantPx = h - 44 - 2;
    const worldPerPx = 2 * camera.position.z * Math.tan(camera.fov * Math.PI / 360) / h;
    lineup.position.y = (feetPx - wantPx) * worldPerPx;
    ground.position.y = -0.74 + lineup.position.y;
  }
  window.addEventListener("resize", resize); resize();

  const clock3 = new THREE.Clock();
  let visible = true, last = 0;
  if ("IntersectionObserver" in window) new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(box);
  const v3 = new THREE.Vector3();

  function frame() {
    requestAnimationFrame(frame);
    if (!visible) return;
    const t = clock3.getElapsedTime(), dt = Math.min(t - last, 0.05); last = t;
    if (!reduce && t > talkAt) {
      talker = (talker + 1 + Math.floor(Math.random() * 3)) % pets.length;   // a different pet each time
      speak(talker, null, t); talkAt = t + 4.5 + Math.random() * 3;
    }
    const r = box.getBoundingClientRect();
    for (const g of pets) {
      const p = g.userData.parts, ph = g.userData.phase, mood = g.userData.mood, i = g.userData.index;
      if (g.userData.hop > 0) { g.userData.hop = Math.max(0, g.userData.hop - dt * 2.4); }
      const hop = Math.sin(g.userData.hop * Math.PI) * 0.35;
      if (g.userData.pose !== "idle" && t > g.userData.poseUntil) { g.userData.pose = "idle"; P.setPose(g, "idle"); }
      if (!reduce) {
        const breathe = Math.sin(t * 1.3 + ph) * 0.012;
        g.position.y = (mood === "sleepy" ? -0.03 + breathe * 0.5 : Math.sin(t * 1.1 + ph) * 0.03) + hop;
        g.scale.set(1 + breathe * 0.4, 1 - breathe * 0.6, 1 + breathe * 0.4);
        const look = mood === "sleepy" ? { x: 0, y: 0 } : { x: pointer.y * -0.12, y: pointer.x * 0.28 };
        p.head.rotation.y += ((g.userData.tilt.y + look.y) - p.head.rotation.y) * 0.08;
        p.head.rotation.x += ((g.userData.tilt.x + look.x) - p.head.rotation.x) * 0.08;
        if (mood !== "sleepy" && t > g.userData.blinkAt) {
          const k = t - g.userData.blinkAt;
          const s = k < 0.08 ? 1 - k / 0.08 * 0.9 : (k < 0.16 ? 0.1 + (k - 0.08) / 0.08 * 0.9 : 1);
          const ey = mood === "surprised" ? 1.18 : (mood === "sulky" ? 0.78 : 1);
          for (const e of p.eyeParts) e.scale.y = s * ey;
          if (k > 0.16) g.userData.blinkAt = t + 2.5 + Math.random() * 3.5;
        }
      } else {
        g.position.y = hop;
      }
      // the bubble follows the head
      const b = bubbles[i];
      if (b.classList.contains("on")) {
        if (t > (g.userData.talkUntil || 0)) b.classList.remove("on");
        else {
          v3.set(g.position.x, lineup.position.y + g.position.y + 1.08, 0).project(camera);
          const half = b.offsetWidth / 2 + 8;
          b.style.left = Math.min(r.width - half, Math.max(half, (v3.x + 1) / 2 * r.width)) + "px";
          b.style.top = ((1 - v3.y) / 2 * r.height - 6) + "px";
        }
      }
    }
    renderer.render(scene, camera);
  }
  frame();
})();
