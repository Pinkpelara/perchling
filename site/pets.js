// Perchlings: the pets, as three.js geometry. Single source of truth for the look.
// Used by web/look-test.html (demo), tools/sprites/sprite.html (frame renderer), and later the app.
// Depends on a global THREE (r128 UMD).
(function (root) {
  const SPECIES = [
    // style: "cute" = baby proportions (big low eyes, blush). "calm" = a little older. "cool" = grown, half-lidded, no blush.
    { id: "antenna", label: "Teal",  style: "cute", body: "#2FB3A3", belly: "#BFE8E0", shade: "#1F7F73", extra: "#7EDCD0" },
    { id: "ears",    label: "Pink",  style: "cute", body: "#EE8FA4", belly: "#F9D0D9", shade: "#C46A7E", extra: "#F3ADBD" },
    { id: "leaf",    label: "Green", style: "calm", body: "#58A64E", belly: "#C6E0B4", shade: "#356F2A", extra: "#7CC46A" },
    { id: "horns",   label: "Gold",  style: "cool", body: "#E0862A", belly: "#F4D2A0", shade: "#A85F16", extra: "#F2B85A" },
  ];
  const MOODS = ["happy", "surprised", "sleepy", "sulky"];
  const POSES = ["idle", "blink", "walk1", "walk2", "squash", "stretch", "sit", "lie", "wave1", "wave2"];
  const EYE = "#1E1B24", MOUTH = "#3B2733", BLUSH = "#F58EA6", TONGUE = "#F27C8F", BROW = "#2A2230";
  const STYLE = {
    cute: { eye: 1.0,  eyeY: 0.02, blush: 0.8,  browAmp: 1.0, browY: 0.20, mouth: 1.0,  lids: false, bodyH: 0.44, headR: 0.56, faceY: -0.06 },
    calm: { eye: 0.88, eyeY: 0.05, blush: 0.45, browAmp: 0.8, browY: 0.20, mouth: 0.85, lids: false, bodyH: 0.46, headR: 0.55, faceY: -0.04 },
    cool: { eye: 0.76, eyeY: 0.09, blush: 0,    browAmp: 0.45, browY: 0.17, mouth: 0.7,  lids: true,  bodyH: 0.5,  headR: 0.52, faceY: -0.02 },
  };

  function materials(THREE, sp) {
    const vinyl = (hex) => new THREE.MeshPhysicalMaterial({ color: new THREE.Color(hex), roughness: 0.3, metalness: 0.03, clearcoat: 0.9, clearcoatRoughness: 0.2 });
    return { body: vinyl(sp.body), shade: vinyl(sp.shade), extra: vinyl(sp.extra), belly: vinyl(sp.belly) };
  }
  function matte(THREE, hex, opts) {
    return new THREE.MeshStandardMaterial(Object.assign({ color: new THREE.Color(hex), roughness: 0.55, metalness: 0.02 }, opts || {}));
  }
  function ball(THREE, mat, pos, scale, segs) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(1, segs || 48, segs || 48), mat);
    m.position.set(pos[0], pos[1], pos[2]);
    if (typeof scale === "number") m.scale.setScalar(scale); else m.scale.set(scale[0], scale[1], scale[2]);
    m.castShadow = true; m.receiveShadow = true; return m;
  }
  function arc(THREE, mat, radius, tube, pos, rotZ, span) {
    const m = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 10, 28, span == null ? Math.PI : span), mat);
    m.position.set(pos[0], pos[1], pos[2]); m.rotation.z = rotZ || 0; return m;
  }

  function makePet(THREE, sp) {
    const st = STYLE[sp.style] || STYLE.cute;
    const g = new THREE.Group();
    const M = materials(THREE, sp);
    const wide = sp.id === "ears";

    const bodyScale = wide ? [0.56, st.bodyH, 0.5] : [0.48, st.bodyH, 0.46];
    const bodyRoot = new THREE.Group(); g.add(bodyRoot);
    bodyRoot.add(ball(THREE, M.body, [0, -0.2, 0], bodyScale));
    bodyRoot.add(ball(THREE, M.belly, [0, -0.25, bodyScale[2] * 0.62], [0.3 * (wide ? 1.15 : 1), 0.24, 0.18]));
    const feet = [ball(THREE, M.shade, [-0.16, -0.66, 0.08], [0.15, 0.085, 0.17], 24), ball(THREE, M.shade, [0.16, -0.66, 0.08], [0.15, 0.085, 0.17], 24)];
    feet.forEach((f) => bodyRoot.add(f));
    const arms = [ball(THREE, M.body, [-(bodyScale[0] - 0.05), -0.16, 0.1], [0.12, 0.13, 0.12], 24), ball(THREE, M.body, [bodyScale[0] - 0.05, -0.16, 0.1], [0.12, 0.13, 0.12], 24)];
    arms.forEach((a) => bodyRoot.add(a));

    const headY = 0.42 + (st.bodyH - 0.44) * 0.8;
    const head = new THREE.Group(); head.position.set(0, headY, 0); g.add(head);
    const headR = st.headR;
    head.add(ball(THREE, M.body, [0, 0, 0], wide ? [headR * 1.07, headR * 0.96, headR * 1.04] : headR));

    const face = new THREE.Group(); face.position.set(0, st.faceY, headR * 0.9); head.add(face);
    const eyes = new THREE.Group(); face.add(eyes); const eyeParts = [];
    for (const sx of [-1, 1]) {
      const eye = new THREE.Group(); eye.position.set(sx * 0.17, st.eyeY, 0);
      eye.add(ball(THREE, matte(THREE, EYE, { roughness: 0.25 }), [0, 0, 0], [0.105 * st.eye, 0.135 * st.eye, 0.07], 24));
      eye.add(ball(THREE, matte(THREE, "#ffffff", { emissive: 0xffffff, emissiveIntensity: 0.7 }), [-0.03 * sx * st.eye, 0.05 * st.eye, 0.065], 0.034 * st.eye, 12));
      eye.add(ball(THREE, matte(THREE, "#ffffff", { emissive: 0xffffff, emissiveIntensity: 0.7 }), [0.035 * sx * st.eye, -0.045 * st.eye, 0.06], 0.016 * st.eye, 10));
      if (st.lids) eye.add(ball(THREE, M.body, [0, 0.075 * st.eye, 0.02], [0.125 * st.eye, 0.075 * st.eye, 0.07], 20));  // half-lidded
      eyes.add(eye); eyeParts.push(eye);
    }
    const sleepyLines = new THREE.Group(); face.add(sleepyLines);
    for (const sx of [-1, 1]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.13 * st.eye, 0.024, 0.02), matte(THREE, EYE));
      m.position.set(sx * 0.17, st.eyeY - 0.02, 0.02); m.rotation.z = sx * -0.18; sleepyLines.add(m);
    }
    const brows = [];
    for (const sx of [-1, 1]) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.11, st.lids ? 0.018 : 0.022, 0.02), matte(THREE, BROW));
      b.position.set(sx * 0.17, st.browY, 0.0); face.add(b); brows.push(b);
    }
    const blush = new THREE.Group(); face.add(blush);
    if (st.blush > 0) for (const sx of [-1, 1]) blush.add(ball(THREE, matte(THREE, BLUSH, { transparent: true, opacity: st.blush }), [sx * 0.31, -0.1, -0.02], [0.085, 0.05, 0.03], 16));

    const mk = st.mouth;
    const smile = arc(THREE, matte(THREE, MOUTH), 0.075 * mk, 0.015, [0, -0.13, 0.02], Math.PI, Math.PI);
    const frown = arc(THREE, matte(THREE, MOUTH), 0.06 * mk, 0.015, [0, -0.18, 0.02], 0, Math.PI * 0.9);
    const open = new THREE.Group(); open.position.set(0, -0.15, 0.02); face.add(open);
    open.add(ball(THREE, matte(THREE, MOUTH, { roughness: 0.3 }), [0, 0, 0], [0.065 * mk, 0.055 * mk, 0.03], 20));
    open.add(ball(THREE, matte(THREE, TONGUE, { roughness: 0.35 }), [0, -0.025 * mk, 0.012], [0.038 * mk, 0.022 * mk, 0.02], 16));
    const oh = ball(THREE, matte(THREE, MOUTH, { roughness: 0.3 }), [0, -0.15, 0.02], [0.04, 0.05, 0.03], 20); face.add(oh);
    const flat = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.014, 0.02), matte(THREE, MOUTH)); flat.position.set(0, -0.14, 0.02); face.add(flat);
    face.add(smile); face.add(frown);

    if (sp.id === "antenna") {
      const stalk = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.04, 0.34, 14), M.shade);
      stalk.position.set(0, headR + 0.12, 0); stalk.castShadow = true; head.add(stalk);
      head.add(ball(THREE, M.extra, [0, headR + 0.34, 0], 0.13, 24));
    }
    if (sp.id === "ears") { head.add(ball(THREE, M.body, [-0.64, 0.12, 0.02], [0.2, 0.16, 0.14])); head.add(ball(THREE, M.body, [0.64, 0.12, 0.02], [0.2, 0.16, 0.14])); }
    if (sp.id === "leaf") {
      const a = ball(THREE, M.extra, [-0.1, headR + 0.06, 0.0], [0.26, 0.14, 0.2]); a.rotation.set(0.5, 0, -0.45); head.add(a);
      const b = ball(THREE, M.shade, [0.13, headR + 0.1, -0.04], [0.22, 0.1, 0.15]); b.rotation.set(0.4, 0, 0.5); head.add(b);
    }
    if (sp.id === "horns") {
      for (const sx of [-1, 1]) {
        const h = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.36, 6), M.shade);
        h.position.set(sx * 0.33, headR - 0.04, 0); h.rotation.z = sx * -0.55; h.castShadow = true; head.add(h);
      }
    }

    g.userData.style = sp.style;
    g.userData.parts = { head, face, eyes, eyeParts, sleepyLines, brows, blush, smile, frown, open, oh, flat, feet, arms, bodyRoot };
    g.userData.armX = bodyScale[0] - 0.05;
    setMood(g, "happy");
    return g;
  }

  // ---- closet -------------------------------------------------------------
  // Items are built in "head space": origin at the point on top of the head, y up,
  // sized for a head radius of 0.55 and scaled to fit each pet. They hang off the
  // head group so every pose moves them too. Names and shelves live in app/closet.json.
  const HAT_SEAT = {   // where a hat sits so the pet's own feature stays in view
    antenna: { tilt: 0.46, y: -0.02 },   // to one side, the antenna stays clear
    ears:    { tilt: 0.0,  y: -0.03 },
    leaf:    { tilt: -0.56, y: 0.0 },    // to the other side, the leaf stays clear
    horns:   { tilt: 0.0,  y: 0.0 },
  };
  const HATS = {
    beanie(THREE) {
      const g = new THREE.Group(), wool = matte(THREE, "#5B57D6", { roughness: 0.85 }), cream = matte(THREE, "#F6EFE3", { roughness: 0.9 });
      g.add(ball(THREE, wool, [0, 0.03, 0], [0.4, 0.8 * 0.4, 0.4], 32));
      const brim = new THREE.Mesh(new THREE.TorusGeometry(0.385, 0.055, 12, 40), cream); brim.rotation.x = Math.PI / 2; brim.position.y = -0.12; g.add(brim);
      g.add(ball(THREE, cream, [0, 0.4, 0], 0.1, 20));
      return g;
    },
    crown(THREE) {
      const g = new THREE.Group(), gold = new THREE.MeshStandardMaterial({ color: new THREE.Color("#F5C242"), roughness: 0.3, metalness: 0.6, side: THREE.DoubleSide });
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.33, 0.22, 32, 1, true), gold); band.position.y = -0.02; g.add(band);
      for (let i = 0; i < 6; i++) {
        const a = i / 6 * Math.PI * 2, pt = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.14, 8), gold);
        pt.position.set(Math.sin(a) * 0.34, 0.16, Math.cos(a) * 0.34); g.add(pt);
      }
      const gems = ["#E64C6A", "#48B7E8", "#E64C6A"];
      gems.forEach((c, i) => g.add(ball(THREE, matte(THREE, c, { roughness: 0.2 }), [(i - 1) * 0.16, 0.0, 0.345], 0.04, 12)));
      return g;
    },
    party(THREE) {
      const g = new THREE.Group();
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.24, 0.5, 32), matte(THREE, "#6C5CE7", { roughness: 0.5 })); cone.position.y = 0.2; g.add(cone);
      g.add(ball(THREE, matte(THREE, "#FFD166", { roughness: 0.8 }), [0, 0.47, 0], 0.07, 16));
      return g;
    },
    chef(THREE) {
      const g = new THREE.Group(), cloth = matte(THREE, "#F4F1EA", { roughness: 0.75 });
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.16, 32), cloth); band.position.y = -0.04; g.add(band);
      g.add(ball(THREE, cloth, [0, 0.22, 0], 0.3, 28));
      g.add(ball(THREE, cloth, [-0.2, 0.16, 0.04], 0.22, 24));
      g.add(ball(THREE, cloth, [0.2, 0.16, 0.04], 0.22, 24));
      return g;
    },
    mushroom(THREE) {
      const g = new THREE.Group(), cap = matte(THREE, "#E24B3F", { roughness: 0.45 }), dot = matte(THREE, "#FFF7EC", { roughness: 0.6 });
      const R = 0.6, ry = 0.58;
      g.add(ball(THREE, cap, [0, 0.02, 0], [R, R * ry, R], 40));
      for (const [x, y, z] of [[0, 0.9, 0.4], [0.7, 0.6, 0.5], [-0.65, 0.55, 0.55], [0.55, 0.45, -0.7], [-0.6, 0.5, -0.6], [0.05, 0.5, -0.85]]) {
        const n = new THREE.Vector3(x, y, z).normalize();
        g.add(ball(THREE, dot, [n.x * R * 1.02, 0.02 + n.y * R * ry * 1.02, n.z * R * 1.02], [0.09, 0.06, 0.09], 12));
      }
      return g;
    },
    flowers(THREE) {
      const g = new THREE.Group();
      const vine = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.045, 10, 40), matte(THREE, "#5FA85A", { roughness: 0.8 })); vine.rotation.x = Math.PI / 2; vine.position.y = -0.14; g.add(vine);
      const petals = ["#FF8FB1", "#FFFFFF", "#C9A7FF"];
      for (let i = 0; i < 6; i++) {
        const a = i / 6 * Math.PI * 2, f = new THREE.Group();
        f.position.set(Math.sin(a) * 0.42, -0.1, Math.cos(a) * 0.42);
        f.add(ball(THREE, matte(THREE, petals[i % 3], { roughness: 0.6 }), [0, 0, 0], [0.11, 0.045, 0.11], 14));
        f.add(ball(THREE, matte(THREE, "#FFD166", { roughness: 0.6 }), [0, 0.03, 0], 0.045, 10));
        g.add(f);
      }
      return g;
    },
  };
  function makeOutfit(THREE, id, sp) {
    const build = HATS[id];
    if (!build) return null;
    const st = STYLE[sp.style] || STYLE.cute, headR = st.headR;
    const top = headR * (sp.id === "ears" ? 0.96 : 1);
    const seat = HAT_SEAT[sp.id] || { tilt: 0, y: 0 };
    const k = headR / 0.55;
    const item = build(THREE); item.scale.setScalar(k); item.position.y = top + seat.y;
    item.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
    const g = new THREE.Group(); g.rotation.z = seat.tilt; g.add(item);   // turning around the head centre keeps it on the head
    g.userData.outfit = id;
    return g;
  }
  function wear(THREE, pet, sp, id) {
    const head = pet.userData.parts.head;
    for (const c of head.children.slice()) if (c.userData.outfit) head.remove(c);
    if (!id) return null;
    const g = makeOutfit(THREE, id, sp);
    if (g) head.add(g);
    return g;
  }

  function setMood(g, mood) {
    const p = g.userData.parts, st = STYLE[g.userData.style] || STYLE.cute;
    g.userData.mood = mood;
    p.eyes.visible = mood !== "sleepy"; p.sleepyLines.visible = mood === "sleepy";
    p.smile.visible = mood === "happy"; p.open.visible = mood === "happy" && !st.lids; p.frown.visible = mood === "sulky";
    p.oh.visible = (mood === "surprised" || mood === "sleepy"); p.flat.visible = false;
    if (st.lids && mood === "happy") { p.smile.visible = true; }
    p.blush.visible = mood !== "sulky";
    const a = st.browAmp;
    const set = (b, sx, y, rz) => { b.position.y = y; b.rotation.z = sx * rz * a; };
    const [L, R] = p.brows;
    if (mood === "happy")     { set(L, -1, st.browY, 0.18);         set(R, 1, st.browY, 0.18); }
    if (mood === "surprised") { set(L, -1, st.browY + 0.05, 0.05);  set(R, 1, st.browY + 0.05, 0.05); }
    if (mood === "sleepy")    { set(L, -1, st.browY - 0.03, 0.1);   set(R, 1, st.browY - 0.03, 0.1); }
    if (mood === "sulky")     { set(L, -1, st.browY - 0.03, -0.35); set(R, 1, st.browY - 0.03, -0.35); }
    const ey = mood === "surprised" ? 1.18 : (mood === "sulky" ? 0.78 : 1);
    for (const e of p.eyeParts) e.scale.set(1, ey, 1);
    if (mood === "surprised") p.oh.scale.set(0.04, 0.05, 0.03); else p.oh.scale.set(0.03, 0.028, 0.025);
    g.userData.tilt = mood === "sulky" ? { x: 0.08, y: 0.55 } : (mood === "sleepy" ? { x: 0.2, y: 0 } : { x: 0, y: 0 });
  }

  function setPose(g, pose) {
    const p = g.userData.parts;
    g.rotation.z = 0; g.position.y = 0; g.scale.set(1, 1, 1);
    for (const f of p.feet) { f.position.set(Math.sign(f.position.x) * 0.16, -0.66, 0.08); f.rotation.set(0, 0, 0); }
    if (p.arms) for (const a of p.arms) { a.position.set(Math.sign(a.position.x) * g.userData.armX, -0.16, 0.1); a.scale.set(0.12, 0.13, 0.12); }
    if (pose === "blink") for (const e of p.eyeParts) e.scale.y *= 0.1;
    if (pose === "sit") {   // feet out front, soles showing, a little settled
      for (const f of p.feet) { f.position.set(Math.sign(f.position.x) * 0.2, -0.56, 0.34); f.rotation.x = -0.9; }
      g.scale.set(1.04, 0.95, 1.04);
    }
    if (pose === "lie") { g.rotation.z = -1.35; g.position.y = -0.18; }   // on its side, head to the right
    if (pose === "wave1" || pose === "wave2") {
      const a = p.arms[1], up = pose === "wave2";
      a.position.set(g.userData.armX + (up ? 0.12 : 0.05), up ? 0.2 : 0.08, 0.14); a.scale.set(0.12, 0.18, 0.12);
    }
    if (pose === "walk1") { p.feet[0].position.z = 0.22; p.feet[1].position.z = -0.06; g.rotation.z = 0.05; g.position.y = 0.03; }
    if (pose === "walk2") { p.feet[0].position.z = -0.06; p.feet[1].position.z = 0.22; g.rotation.z = -0.05; g.position.y = 0.03; }
    if (pose === "squash") { g.scale.set(1.08, 0.9, 1.08); }
    if (pose === "stretch") { g.scale.set(0.95, 1.08, 0.95); g.position.y = 0.06; }
  }

  // Shared stage lighting so the demo and the sprite renderer match.
  function addLights(THREE, scene, opts) {
    const o = opts || {};
    scene.add(new THREE.HemisphereLight(0xffffff, 0x2a1840, 0.32));
    const key = new THREE.DirectionalLight(0xfff4e6, 1.45); key.position.set(3, 5.5, 4); key.castShadow = true;
    const s = o.shadowSize || 6;
    key.shadow.mapSize.set(o.shadowMap || 2048, o.shadowMap || 2048);
    key.shadow.camera.left = -s; key.shadow.camera.right = s; key.shadow.camera.top = s; key.shadow.camera.bottom = -s;
    key.shadow.camera.near = 1; key.shadow.camera.far = 20; key.shadow.radius = 4;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xc8b6ff, 0.22); fill.position.set(-4, 2, 3); scene.add(fill);
    const rim = new THREE.DirectionalLight(0xff9ed6, 0.6); rim.position.set(0, 3, -5); scene.add(rim);
  }
  function setupRenderer(THREE, renderer) {
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.92;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }

  root.Perchlings = { SPECIES, MOODS, POSES, STYLE, HATS, makePet, makeOutfit, wear, setMood, setPose, addLights, setupRenderer };
})(typeof window !== "undefined" ? window : globalThis);
