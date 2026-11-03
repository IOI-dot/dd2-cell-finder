import { Badge } from "./ui";
import { Slider } from "./ui";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { LAYER_COLOURS, Panel, Waiting } from "./panels";
import { useEvidence } from "./useEvidence";

type Layout = { cell: string; width_um: number; height_um: number; layers: Record<string, number[][][]> };

/* A display stack only: each layer's z and height exist to separate the masks, and say nothing about the process. */
const STACK: Record<string, [number, number]> = { nwell: [-0.06, 0.03], diff: [0, 0.05], poly: [0.08, 0.1], licon: [0.05, 0.24], li1: [0.29, 0.08], mcon: [0.37, 0.14], met1: [0.51, 0.14] };

export function Cell3D({ cell }: { cell: string }) {
  const { data, error } = useEvidence<Layout>(cell, "layout");
  const box = useRef<HTMLDivElement>(null);
  const scene = useRef<{ groups: Record<string, THREE.Group> } | null>(null);
  const [off, setOff] = useState<Set<string>>(new Set(["nwell"]));
  const [spread, setSpread] = useState(2);

  useEffect(() => {
    const host = box.current;
    if (!data || !host) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, 420);
    host.appendChild(renderer.domElement);
    const world = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, host.clientWidth / 420, 0.05, 100);
    const size = Math.max(data.width_um, data.height_um);
    camera.position.set(data.width_um / 2 + size * 0.2, -size * 1.0, size * 1.15);
    camera.up.set(0, 0, 1);
    world.add(new THREE.AmbientLight(0xffffff, 1.5));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(2, -3, 5);
    world.add(sun);
    const groups: Record<string, THREE.Group> = {};
    for (const [layer, polys] of Object.entries(data.layers)) {
      const [, h] = STACK[layer] ?? [0, 0.05];
      const material = new THREE.MeshStandardMaterial({ color: LAYER_COLOURS[layer], transparent: layer === "nwell", opacity: layer === "nwell" ? 0.2 : 1, roughness: 0.45, metalness: layer.startsWith("met") || layer === "li1" ? 0.4 : 0.1 });
      const g = new THREE.Group();
      for (const p of polys) {
        const shape = new THREE.Shape(p.map(([x, y]) => new THREE.Vector2(x, y)));
        g.add(new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: false }), material));
      }
      g.name = layer;
      world.add(g);
      groups[layer] = g;
    }
    scene.current = { groups };
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(data.width_um / 2, data.height_um / 2, 0.2);
    controls.enableDamping = true;
    controls.autoRotate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    controls.autoRotateSpeed = 0.7;
    renderer.domElement.addEventListener("pointerdown", () => { controls.autoRotate = false; });
    let frame = 0;
    const tick = () => { controls.update(); renderer.render(world, camera); frame = requestAnimationFrame(tick); };
    tick();
    const resize = new ResizeObserver(() => {
      camera.aspect = host.clientWidth / 420;
      camera.updateProjectionMatrix();
      renderer.setSize(host.clientWidth, 420);
    });
    resize.observe(host);
    return () => {
      cancelAnimationFrame(frame); resize.disconnect(); controls.dispose();
      world.traverse((o) => { if (o instanceof THREE.Mesh) o.geometry.dispose(); });
      renderer.dispose(); host.removeChild(renderer.domElement); scene.current = null;
    };
  }, [data]);

  useEffect(() => {
    if (!scene.current) return;
    for (const [layer, g] of Object.entries(scene.current.groups)) {
      g.visible = !off.has(layer);
      g.position.z = (STACK[layer]?.[0] ?? 0) * (1 + spread * 1.4);
    }
  }, [off, spread, data]);

  if (!data) return <Waiting error={error} />;
  return (
    <Panel title="Cell in 3D" note={`${data.width_um} × ${data.height_um} µm · drag to orbit`} wide>
      <div ref={box} data-testid="cell-3d" className="relative h-[420px] w-full overflow-hidden rounded-md bg-background">
        <Badge variant="outline" className="absolute left-2 top-2 z-10 bg-background/80 text-xs">Illustrative layer extrusion, not a fabrication cross-section</Badge>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {Object.keys(STACK).map((l) => (
          <button key={l} aria-pressed={!off.has(l)} onClick={() => setOff((s) => { const n = new Set(s); if (n.has(l)) n.delete(l); else n.add(l); return n; })}
            className={`inline-flex items-center gap-1.5 min-h-11 rounded-md border px-2 py-0.5 font-mono text-xs lg:min-h-7 ${off.has(l) ? "opacity-40" : ""}`}>
            <i className="size-2.5 rounded-sm" style={{ background: LAYER_COLOURS[l] }} />{l}
          </button>
        ))}
        <label className="ml-auto flex w-44 items-center gap-2 text-xs text-muted-foreground">Explode
          <Slider aria-label="Explode the layers" min={0} max={8} step={0.1} value={[spread]} onValueChange={(v) => setSpread(Array.isArray(v) ? v[0] : (v as number))} />
        </label>
      </div>
    </Panel>
  );
}
