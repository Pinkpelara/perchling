// Perchlings shop site. Two things to fill in before launch, nothing else needs touching:
const CONFIG = {
  buyUrl: "",                 // the checkout link from the payment provider (Lemon Squeezy, Gumroad, ...). Empty = "Adoptions open soon".
  contact: "",                // an email address for the footer. Empty = no contact link.
};

(() => {
  // --- buy buttons and contact
  for (const a of document.querySelectorAll("[data-buy]")) {
    if (CONFIG.buyUrl) { a.href = CONFIG.buyUrl; a.rel = "noopener"; }
    else { a.textContent = a.textContent.includes("$") ? "Adoptions open soon" : "Soon"; a.href = "#price"; }
  }
  const slot = document.getElementById("contact-slot");
  if (slot && CONFIG.contact) {
    const a = document.createElement("a"); a.href = "mailto:" + CONFIG.contact; a.textContent = "Write to us"; slot.append(" · ", a);
  }

  // --- the live stage: four pets, blink, breathe, watch the cursor; click one to try a hat on it
  const box = document.getElementById("stage"), canvas = document.getElementById("c");
  const P = window.Perchlings;
  let renderer;
  try {
    if (!window.THREE || !P) throw new Error("no three");
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch (e) {
    box.classList.add("no-webgl"); return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  P.setupRenderer(THREE, renderer);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x120820);
  scene.fog = new THREE.Fog(0x120820, 9, 17);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);
  P.addLights(THREE, scene);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: 0x0f0619, roughness: 1, metalness: 0 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.74; ground.receiveShadow = true; scene.add(ground);

  const START = { antenna: "happy", ears: "sleepy", leaf: "happy", horns: "sulky" };
  const HATS = [""].concat(Object.keys(P.HATS));
  const lineup = new THREE.Group(); scene.add(lineup);
  const pets = P.SPECIES.map((sp, i) => {
    const g = P.makePet(THREE, sp); P.setMood(g, START[sp.id] || "happy");
    g.userData.index = i; g.userData.sp = sp; g.userData.hat = 0; g.userData.hop = 0;
    g.userData.blinkAt = 2 + Math.random() * 3; g.userData.phase = Math.random() * Math.PI * 2;
    g.position.x = (i - 1.5) * 1.9; lineup.add(g); return g;
  });

  function nextHat(g) {
    g.userData.hat = (g.userData.hat + 1) % HATS.length;
    P.wear(THREE, g, g.userData.sp, HATS[g.userData.hat]);
    P.setMood(g, g.userData.hat ? "happy" : "surprised");
    g.userData.hop = 1;
  }
  document.getElementById("hats-off").addEventListener("click", () => {
    for (const g of pets) { g.userData.hat = 0; P.wear(THREE, g, g.userData.sp, ""); P.setMood(g, START[g.userData.sp.id] || "happy"); }
  });

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
  });
  canvas.addEventListener("pointerup", (e) => {
    const [x, y] = toNdc(e); ndc.set(x, y);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(lineup.children, true)[0];
    if (hit) { let o = hit.object; while (o && o.userData.index === undefined) o = o.parent; if (o) nextHat(o); }
  });

  function resize() {
    const w = box.clientWidth, h = box.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const narrow = w < 640;
    camera.position.set(0, narrow ? 0.9 : 0.7, narrow ? 11.5 : 7.6); camera.lookAt(0, 0.0, 0);
  }
  window.addEventListener("resize", resize); resize();

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clock = new THREE.Clock();
  let visible = true, last = 0;
  if ("IntersectionObserver" in window) new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(box);

  function frame() {
    requestAnimationFrame(frame);
    if (!visible) return;
    const t = clock.getElapsedTime(), dt = Math.min(t - last, 0.05); last = t;
    for (const g of pets) {
      const p = g.userData.parts, ph = g.userData.phase, mood = g.userData.mood;
      if (g.userData.hop > 0) { g.userData.hop = Math.max(0, g.userData.hop - dt * 2.4); }
      const hop = Math.sin(g.userData.hop * Math.PI) * 0.35;
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
    }
    renderer.render(scene, camera);
  }
  frame();
})();
