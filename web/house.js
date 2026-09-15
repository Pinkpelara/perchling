// Perchlings: the house, as three.js geometry. Same vinyl-toy look as the pets.
// Two views: "closed" (the outside, small, sits on the taskbar) and "open" (front wall off, four rooms, a dollhouse).
// Furniture pieces are built separately so each can be rendered as its own layer and sold in the shop.
// Units: a pet is about 1.5 tall. The house is 7.2 wide; rooms are 2.5 high.
(function (root) {
  const W = 7.2, ROOM_H = 2.5, WALL = 0.16, DEPTH = 3.2;
  const ROOMS = {
    living:   { floor: 0,      x: [-W / 2 + WALL, -0.08], name: "Living room" },
    kitchen:  { floor: 0,      x: [0.08, W / 2 - WALL],   name: "Kitchen" },
    bedroom:  { floor: 1,      x: [-W / 2 + WALL, -0.08], name: "Bedroom" },
    bathroom: { floor: 1,      x: [0.08, W / 2 - WALL],   name: "Bathroom" },
  };
  const STYLES = {
    cozy: { shell: "#F1D9B8", trim: "#D9AE7E", roof: "#D9506E", roofEdge: "#B03A55", door: "#5B57D6", frame: "#FFFFFF", floorWood: "#C48D55", stairs: "#B07C4A", chimney: "#A57454", glass: "#9FD8EA", flat: false },
    loft: { shell: "#2E2C3A", trim: "#1B1A24", roof: "#3A3850", roofEdge: "#15141C", door: "#E0862A", frame: "#111018", floorWood: "#8B5E3C", stairs: "#6E4A2E", chimney: "#3A3850", glass: "#6FA8C8", flat: true },
  };
  const PALETTE = {
    shell: "#F1D9B8", trim: "#D9AE7E", roof: "#D9506E", roofEdge: "#B03A55", door: "#5B57D6", frame: "#FFFFFF",
    floorWood: "#C48D55", floorTile: "#A9D3DE", wallLiving: "#F2F2F2", wallKitchen: "#F2F2F2", wallBedroom: "#F2F2F2", wallBathroom: "#F2F2F2",   // walls render neutral; the app tints each room
    stairs: "#B07C4A", chimney: "#A57454", glass: "#9FD8EA",
  };
  const WALLS = { living: "wallLiving", kitchen: "wallKitchen", bedroom: "wallBedroom", bathroom: "wallBathroom" };

  function mat(THREE, hex, opts) {
    return new THREE.MeshStandardMaterial(Object.assign({ color: new THREE.Color(hex), roughness: 0.6, metalness: 0.02 }, opts || {}));
  }
  function vinyl(THREE, hex) {
    return new THREE.MeshPhysicalMaterial({ color: new THREE.Color(hex), roughness: 0.35, metalness: 0.03, clearcoat: 0.8, clearcoatRoughness: 0.25 });
  }
  function box(THREE, m, w, h, d, x, y, z) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); b.castShadow = true; b.receiveShadow = true; return b;
  }
  function cyl(THREE, m, rt, rb, h, x, y, z, segs) {
    const c = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, segs || 24), m); c.position.set(x, y, z); c.castShadow = true; c.receiveShadow = true; return c;
  }
  function ball(THREE, m, r, x, y, z, sx, sy, sz) {
    const b = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 28), m); b.position.set(x, y, z); if (sx) b.scale.set(sx, sy, sz); b.castShadow = true; b.receiveShadow = true; return b;
  }

  // ---- the shell, shared by both views
  function makeShell(THREE, open, walls, style) {
    const P = Object.assign({}, PALETTE, STYLES[style || "cozy"] || STYLES.cozy);
    const g = new THREE.Group();
    const shell = vinyl(THREE, P.shell), trim = vinyl(THREE, P.trim);
    const H = ROOM_H * 2;
    // floors and ceilings
    const floorM = mat(THREE, P.floorWood);
    for (const [m, y] of [[floorM, WALL / 2], [floorM, ROOM_H + WALL / 2], [shell, H + WALL / 2]]) {
      const slab = box(THREE, m, W, WALL, DEPTH, 0, y, 0); slab.castShadow = false; g.add(slab);                        // floors don't throw the rooms below into shadow
    }
    // side walls and the middle wall (with a doorway on each floor)
    g.add(box(THREE, shell, WALL, H + WALL, DEPTH, -W / 2 + WALL / 2, H / 2, 0));
    g.add(box(THREE, shell, WALL, H + WALL, DEPTH, W / 2 - WALL / 2, H / 2, 0));
    for (const f of [0, 1]) {
      const y0 = f * ROOM_H;
      g.add(box(THREE, shell, WALL, ROOM_H, DEPTH * 0.45, 0, y0 + ROOM_H / 2, -DEPTH * 0.275));          // back part of the middle wall
      g.add(box(THREE, shell, WALL, 0.6, DEPTH * 0.55, 0, y0 + ROOM_H - 0.3, DEPTH * 0.225));            // above the doorway
    }
    // back walls per room, coloured
    for (const id in ROOMS) {
      const r = ROOMS[id], c = (walls && walls[id]) || PALETTE[WALLS[id]];
      const x0 = r.x[0], x1 = r.x[1];
      const wallM = mat(THREE, c, { roughness: 0.95 });
      const wall = box(THREE, wallM, x1 - x0, ROOM_H, WALL, (x0 + x1) / 2, r.floor * ROOM_H + ROOM_H / 2, -DEPTH / 2 + WALL / 2); wall.receiveShadow = false; g.add(wall);
    }
    // a staircase along the back wall of the living room, up toward the middle
    for (let i = 0; i < 8; i++) {
      g.add(box(THREE, mat(THREE, P.stairs), 0.3, 0.2, 0.7, -2.7 + i * 0.3, WALL + 0.1 + i * 0.29, -DEPTH / 2 + WALL + 0.36));
    }
    // roof: a gable with a chimney, or a flat roof with a deck for the loft
    const roofM = vinyl(THREE, P.roof);
    const roof = new THREE.Group();
    const half = W / 2 + 0.3, rise = 1.7, len = DEPTH + 0.6;
    if (P.flat) {
      roof.add(box(THREE, roofM, W + 0.6, 0.3, len, 0, H + WALL + 0.15, 0));
      roof.add(box(THREE, mat(THREE, P.roofEdge), W + 0.7, 0.08, len + 0.05, 0, H + WALL + 0.32, 0));
      for (const x of [-3.3, 3.3]) roof.add(box(THREE, mat(THREE, P.roofEdge), 0.06, 0.5, len - 0.2, x, H + WALL + 0.55, 0));       // a rail
      roof.add(box(THREE, mat(THREE, P.roofEdge), W + 0.5, 0.05, 0.05, 0, H + WALL + 0.8, len / 2 - 0.1));
      roof.add(ball(THREE, vinyl(THREE, "#58A64E"), 0.3, -2.4, H + WALL + 0.6, 0.6)); roof.add(cyl(THREE, mat(THREE, "#8B5E3C"), 0.18, 0.14, 0.3, -2.4, H + WALL + 0.45, 0.6));   // a planter
    } else {
      const shape = new THREE.Shape(); shape.moveTo(-half, 0); shape.lineTo(0, rise); shape.lineTo(half, 0); shape.lineTo(-half, 0);
      const prism = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: len, bevelEnabled: false }), roofM);
      prism.position.set(0, H + WALL, -len / 2); prism.castShadow = true; prism.receiveShadow = true; roof.add(prism);
      roof.add(box(THREE, mat(THREE, P.roofEdge), W + 0.7, 0.12, len + 0.05, 0, H + WALL + 0.02, 0));
      roof.add(box(THREE, mat(THREE, P.chimney), 0.45, 1.2, 0.45, 2.2, H + WALL + 1.0, -0.6));
    }
    g.add(roof);
    if (!open) {
      // the front wall with a door and windows
      const front = box(THREE, shell, W, H, WALL, 0, H / 2, DEPTH / 2 - WALL / 2); g.add(front);
      const doorM = vinyl(THREE, P.door);
      g.add(box(THREE, doorM, 0.9, 1.5, 0.08, 0, 0.75 + WALL, DEPTH / 2 + 0.02));
      const arch = cyl(THREE, doorM, 0.45, 0.45, 0.08, 0, 1.5 + WALL, DEPTH / 2 + 0.02, 24); arch.rotation.x = Math.PI / 2; g.add(arch);
      g.add(ball(THREE, mat(THREE, "#FFD166"), 0.06, 0.3, 0.85 + WALL, DEPTH / 2 + 0.07));
      g.add(box(THREE, mat(THREE, P.trim), 1.3, 0.14, 0.5, 0, WALL + 0.07, DEPTH / 2 + 0.2));       // a step
      const wins = P.flat ? [[-2.0, 1.4, 1.6, 1.1], [2.0, 1.4, 1.6, 1.1], [-2.0, ROOM_H + 1.4, 1.6, 1.1], [2.0, ROOM_H + 1.4, 1.6, 1.1]] : [[-2.2, 1.4, 1, 1], [2.2, 1.4, 1, 1], [-2.2, ROOM_H + 1.4, 1, 1], [2.2, ROOM_H + 1.4, 1, 1], [0, ROOM_H + 1.4, 1, 1]];
      for (const [x, y, ww, wh] of wins) {
        g.add(box(THREE, mat(THREE, P.frame), ww, wh, 0.06, x, y, DEPTH / 2 + 0.01));
        g.add(box(THREE, mat(THREE, P.glass, { roughness: 0.2 }), ww - 0.2, wh - 0.2, 0.06, x, y, DEPTH / 2 + 0.03));
        g.add(box(THREE, mat(THREE, P.frame), 0.06, wh - 0.2, 0.07, x, y, DEPTH / 2 + 0.04));
        g.add(box(THREE, mat(THREE, P.frame), ww - 0.2, 0.06, 0.07, x, y, DEPTH / 2 + 0.04));
      }
    }
    g.userData.rooms = ROOMS;
    return g;
  }

  // ---- furniture, each a group placed in its room. Build once, position by room.
  const FURNITURE = {
    bed(THREE) {
      const g = new THREE.Group(), wood = vinyl(THREE, "#C9A27A");
      g.add(box(THREE, wood, 1.7, 0.3, 1.1, 0, 0.15, 0));
      g.add(box(THREE, mat(THREE, "#FFFFFF", { roughness: 0.9 }), 1.6, 0.18, 1.0, 0, 0.39, 0));
      g.add(box(THREE, mat(THREE, "#C4B0FF", { roughness: 0.9 }), 1.6, 0.14, 0.7, 0.1, 0.55, 0.05));         // blanket
      g.add(ball(THREE, mat(THREE, "#FFFFFF", { roughness: 0.9 }), 0.2, -0.6, 0.55, 0, 1.2, 0.6, 1.4));      // pillow
      g.add(box(THREE, wood, 0.12, 0.9, 1.1, -0.8, 0.45, 0));                                                 // headboard
      return g;
    },
    lamp(THREE) {
      const g = new THREE.Group();
      g.add(cyl(THREE, mat(THREE, "#8E89A8"), 0.18, 0.22, 0.06, 0, 0.03, 0));
      g.add(cyl(THREE, mat(THREE, "#8E89A8"), 0.03, 0.03, 1.1, 0, 0.6, 0));
      g.add(cyl(THREE, mat(THREE, "#FFE9A8", { emissive: 0xffd88a, emissiveIntensity: 0.5 }), 0.22, 0.32, 0.36, 0, 1.25, 0));
      return g;
    },
    rug(THREE) {
      const g = new THREE.Group();
      g.add(cyl(THREE, mat(THREE, "#F58EA6", { roughness: 0.95 }), 0.95, 0.95, 0.03, 0, 0.015, 0, 40));
      g.add(cyl(THREE, mat(THREE, "#FFF1D6", { roughness: 0.95 }), 0.6, 0.6, 0.035, 0, 0.02, 0, 40));
      return g;
    },
    couch(THREE) {
      const g = new THREE.Group(), cloth = mat(THREE, "#5B57D6", { roughness: 0.85 }), cushion = mat(THREE, "#7B78E8", { roughness: 0.9 });
      g.add(box(THREE, cloth, 2.0, 0.45, 0.9, 0, 0.3, 0));
      g.add(box(THREE, cloth, 2.0, 0.6, 0.25, 0, 0.75, -0.32));
      g.add(box(THREE, cloth, 0.25, 0.7, 0.9, -0.9, 0.5, 0)); g.add(box(THREE, cloth, 0.25, 0.7, 0.9, 0.9, 0.5, 0));
      g.add(box(THREE, cushion, 0.8, 0.14, 0.75, -0.42, 0.6, 0.05)); g.add(box(THREE, cushion, 0.8, 0.14, 0.75, 0.42, 0.6, 0.05));
      return g;
    },
    tv(THREE) {
      const g = new THREE.Group(), dark = mat(THREE, "#2B2540", { roughness: 0.4 });
      g.add(box(THREE, vinyl(THREE, "#C9A27A"), 1.5, 0.5, 0.5, 0, 0.25, 0));
      g.add(box(THREE, dark, 1.3, 0.8, 0.08, 0, 0.95, 0));
      g.add(box(THREE, mat(THREE, "#BFD4FF", { emissive: 0x9fc0ff, emissiveIntensity: 0.5, roughness: 0.3 }), 1.15, 0.65, 0.02, 0, 0.95, 0.05));
      return g;
    },
    plant(THREE) {
      const g = new THREE.Group();
      g.add(cyl(THREE, vinyl(THREE, "#E0862A"), 0.22, 0.17, 0.4, 0, 0.2, 0));
      g.add(ball(THREE, vinyl(THREE, "#58A64E"), 0.36, 0, 0.75, 0)); g.add(ball(THREE, vinyl(THREE, "#7CC46A"), 0.26, 0.2, 0.95, 0.1)); g.add(ball(THREE, vinyl(THREE, "#356F2A"), 0.22, -0.22, 0.9, -0.05));
      return g;
    },
    table(THREE) {
      const g = new THREE.Group(), wood = vinyl(THREE, "#D9B58A");
      g.add(cyl(THREE, wood, 0.7, 0.7, 0.08, 0, 0.78, 0, 32)); g.add(cyl(THREE, wood, 0.08, 0.14, 0.75, 0, 0.38, 0));
      for (const x of [-0.9, 0.9]) { g.add(cyl(THREE, wood, 0.22, 0.22, 0.06, x, 0.45, 0)); g.add(cyl(THREE, wood, 0.04, 0.05, 0.42, x, 0.21, 0)); }
      return g;
    },
    fridge(THREE) {
      const g = new THREE.Group(), white = vinyl(THREE, "#F4F1EA");
      g.add(box(THREE, white, 0.9, 1.9, 0.8, 0, 0.95, 0));
      g.add(box(THREE, mat(THREE, "#8E89A8"), 0.05, 0.5, 0.05, 0.3, 1.2, 0.42)); g.add(box(THREE, mat(THREE, "#8E89A8"), 0.05, 0.3, 0.05, 0.3, 0.55, 0.42));
      g.add(box(THREE, mat(THREE, "#DDD9E8"), 0.9, 0.03, 0.82, 0, 0.9, 0));
      return g;
    },
    stove(THREE) {
      const g = new THREE.Group(), white = vinyl(THREE, "#F4F1EA");
      g.add(box(THREE, white, 1.0, 0.9, 0.7, 0, 0.45, 0));
      g.add(box(THREE, mat(THREE, "#2B2540"), 0.95, 0.04, 0.65, 0, 0.92, 0));
      for (const [x, z] of [[-0.25, -0.15], [0.25, -0.15], [-0.25, 0.18], [0.25, 0.18]]) g.add(cyl(THREE, mat(THREE, "#6B6685"), 0.14, 0.14, 0.02, x, 0.95, z));
      g.add(box(THREE, mat(THREE, "#BFD4FF", { roughness: 0.3 }), 0.7, 0.35, 0.02, 0, 0.42, 0.36));
      return g;
    },
    tub(THREE) {
      const g = new THREE.Group(), white = vinyl(THREE, "#FFFFFF");
      const t = box(THREE, white, 1.7, 0.7, 0.85, 0, 0.35, 0); g.add(t);
      g.add(box(THREE, mat(THREE, "#BFE3F0", { roughness: 0.2 }), 1.5, 0.05, 0.65, 0, 0.62, 0));
      g.add(cyl(THREE, mat(THREE, "#8E89A8"), 0.03, 0.03, 0.5, -0.7, 0.9, -0.2)); g.add(cyl(THREE, mat(THREE, "#8E89A8"), 0.06, 0.06, 0.05, -0.55, 1.05, -0.2));
      for (let i = 0; i < 5; i++) g.add(ball(THREE, mat(THREE, "#FFFFFF", { transparent: true, opacity: 0.85 }), 0.07 + (i % 3) * 0.02, -0.4 + i * 0.2, 0.75 + (i % 2) * 0.12, 0.1));
      return g;
    },
    curtain(THREE) {
      const g = new THREE.Group();
      const rod = cyl(THREE, mat(THREE, "#8E89A8"), 0.03, 0.03, 2.2, 0, 2.25, 0); rod.rotation.z = Math.PI / 2; g.add(rod);
      for (let i = 0; i < 11; i++) g.add(box(THREE, mat(THREE, i % 2 ? "#FFFFFF" : "#BFE3F0", { roughness: 0.95 }), 0.2, 2.15, 0.04, -1.0 + i * 0.2, 1.1, 0.05));   // floor to rod: nothing shows
      return g;
    },
    sink(THREE) {
      const g = new THREE.Group(), white = vinyl(THREE, "#FFFFFF");
      g.add(cyl(THREE, white, 0.12, 0.16, 0.7, 0, 0.35, 0)); g.add(ball(THREE, white, 0.36, 0, 0.75, 0, 1, 0.45, 1));
      g.add(cyl(THREE, mat(THREE, "#8E89A8"), 0.03, 0.03, 0.3, 0, 1.0, -0.2));
      g.add(box(THREE, mat(THREE, "#BFE3F0", { roughness: 0.2 }), 0.7, 0.7, 0.04, 0, 1.6, -0.3));            // mirror
      return g;
    },
    poster(THREE) {
      const g = new THREE.Group();
      g.add(box(THREE, mat(THREE, "#FFFFFF"), 0.9, 1.1, 0.03, 0, 0, 0));
      g.add(box(THREE, mat(THREE, "#FFD166"), 0.76, 0.96, 0.02, 0, 0, 0.02));
      g.add(ball(THREE, vinyl(THREE, "#2FB3A3"), 0.22, -0.05, 0.05, 0.05)); g.add(ball(THREE, vinyl(THREE, "#2FB3A3"), 0.16, -0.05, 0.38, 0.05));
      return g;
    },
    fishtank(THREE) {
      const g = new THREE.Group();
      g.add(box(THREE, vinyl(THREE, "#C9A27A"), 1.1, 0.7, 0.6, 0, 0.35, 0));
      g.add(box(THREE, mat(THREE, "#9FD8EA", { transparent: true, opacity: 0.55, roughness: 0.1 }), 1.0, 0.7, 0.5, 0, 1.05, 0));
      g.add(ball(THREE, vinyl(THREE, "#E0862A"), 0.09, -0.2, 1.05, 0, 1.4, 1, 0.8)); g.add(ball(THREE, vinyl(THREE, "#EE8FA4"), 0.07, 0.25, 1.2, 0.05, 1.4, 1, 0.8));
      return g;
    },
  };
  // where each piece lives: room, x within the room (0..1 across), and how far back (0 front .. 1 back), plus a wall height for wall things
  const PLACEMENT = {
    bed: { room: "bedroom", x: 0.35, z: 0.55 }, lamp: { room: "bedroom", x: 0.82, z: 0.6 }, rug: { room: "living", x: 0.5, z: 0.55 },
    couch: { room: "living", x: 0.55, z: 0.75 }, tv: { room: "living", x: 0.16, z: 0.85 }, plant: { room: "living", x: 0.92, z: 0.8 },
    table: { room: "kitchen", x: 0.42, z: 0.55 }, fridge: { room: "kitchen", x: 0.86, z: 0.85 }, stove: { room: "kitchen", x: 0.14, z: 0.85 },
    tub: { room: "bathroom", x: 0.62, z: 0.7 }, curtain: { room: "bathroom", x: 0.62, z: 0.55 }, sink: { room: "bathroom", x: 0.15, z: 0.85 },
    poster: { room: "bedroom", x: 0.75, z: 1.0, wall: 1.6 }, fishtank: { room: "kitchen", x: 0.6, z: 0.9 },
  };

  function placeFurniture(THREE, id) {
    const build = FURNITURE[id], p = PLACEMENT[id];
    if (!build || !p) return null;
    const g = build(THREE), r = ROOMS[p.room];
    const x = r.x[0] + (r.x[1] - r.x[0]) * p.x;
    const z = DEPTH / 2 - WALL - (DEPTH - 2 * WALL) * p.z;
    g.position.set(x, r.floor * ROOM_H + WALL + (p.wall || 0), p.wall ? -DEPTH / 2 + WALL + 0.03 : z);
    g.userData.furniture = id;
    return g;
  }

  // a spot on each room's floor where a pet stands, as a fraction across the room, and what it does there
  const SPOTS = {
    living: { x: 0.5, z: 0.35 }, kitchen: { x: 0.42, z: 0.3 }, bedroom: { x: 0.35, z: 0.45 }, bathroom: { x: 0.62, z: 0.74 },   // the bath is behind the curtain
  };
  function roomFloor(id) {
    const r = ROOMS[id]; return { y: r.floor * ROOM_H + WALL, x0: r.x[0], x1: r.x[1], floor: r.floor };
  }

  root.PerchlingHouse = { W, ROOM_H, WALL, DEPTH, ROOMS, PALETTE, STYLES, FURNITURE, PLACEMENT, SPOTS, makeShell, placeFurniture, roomFloor };
})(typeof window !== "undefined" ? window : globalThis);
