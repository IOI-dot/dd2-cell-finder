import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Panel, Waiting } from "./panels";
import { useEvidence } from "./useEvidence";

type T = { pin: string; table: string; index_1: number[]; index_2: number[]; values: number[][]; shipped?: number[][] };
type Timing = { cell: string; tables: T[] };

function surface(t: T, values: number[][], top: number, colour: boolean) {
  const n = t.index_1.length, m = t.index_2.length;
  const pos: number[] = [], col: number[] = [], idx: number[] = [];
  const c = new THREE.Color();
  values.forEach((row, i) => row.forEach((v, j) => {
    pos.push(i / (n - 1) * 2 - 1, j / (m - 1) * 2 - 1, Math.log10(1 + (v / top) * 99) / 2);
    c.setHSL(0.55 - 0.55 * (v / top), 0.8, 0.55);
    col.push(c.r, c.g, c.b);
  }));
  for (let i = 0; i < n - 1; i++) for (let j = 0; j < m - 1; j++) {
    const a = i * m + j;
    idx.push(a, a + m, a + 1, a + 1, a + m, a + m + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return new THREE.Mesh(g, colour ? new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.6 })
    : new THREE.MeshBasicMaterial({ color: 0xf2f5fa, wireframe: true, transparent: true, opacity: 0.45 }));
}

/* Each vertex is one measured table entry: no point between them is drawn from a fit. */
export function TimingView({ cell }: { cell: string }) {
  const { data, error } = useEvidence<Timing>(cell, "timing");
  const [k, setK] = useState(0);
  const [hd, setHd] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const t = data?.tables[k];

  useEffect(() => {
    const host = box.current;
    if (!t || !host) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setSize(host.clientWidth, 340);
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(40, host.clientWidth / 340, 0.01, 50);
    cam.position.set(2.6, -2.6, 2.1);
    cam.up.set(0, 0, 1);
    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.8);
    sun.position.set(1, -2, 3);
    scene.add(sun);
    const top = Math.max(...t.values.flat(), ...(t.shipped?.flat() ?? []));
    scene.add(surface(t, t.values, top, true));
    if (hd && t.shipped) scene.add(surface(t, t.shipped, top, false));
    const controls = new OrbitControls(cam, renderer.domElement);
    controls.enableDamping = true;
    let f = 0;
    const tick = () => { controls.update(); renderer.render(scene, cam); f = requestAnimationFrame(tick); };
    tick();
    return () => { cancelAnimationFrame(f); controls.dispose(); renderer.dispose(); host.removeChild(renderer.domElement); };
  }, [t, hd]);

  if (error) return <Panel title="Timing surface"><p className="text-xs text-muted-foreground">Timing tables exist for the six reference cells at this milestone.</p></Panel>;
  if (!data || !t) return <Waiting />;
  return (
    <Panel title="Timing surface" note={`${data.cell}: ${t.table} of pin ${t.pin}, slew × load, ${t.index_1.length * t.index_2.length} measured points`} wide>
      <div className="flex flex-wrap gap-1">
        {data.tables.map((x, i) => <Button key={i} size="sm" variant={i === k ? "default" : "outline"} className="h-6 px-2 font-mono text-[11px]" onClick={() => setK(i)}>{x.pin} {x.table}</Button>)}
        <Button size="sm" variant="ghost" className="ml-auto h-6 px-2 text-[11px]" aria-pressed={hd} onClick={() => setHd((v) => !v)}>{hd ? "Hide" : "Show"} shipped Liberty</Button>
      </div>
      <div ref={box} data-testid="timing-surface" className="h-[340px] w-full overflow-hidden rounded-md bg-background" />
      <p className="text-xs text-muted-foreground">Colour: our characterizer on the installed layout. White mesh: the shipped Liberty. Height is logarithmic, so the two can be told apart across the table.</p>
    </Panel>
  );
}
