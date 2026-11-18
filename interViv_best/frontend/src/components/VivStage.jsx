import React, { useEffect, useRef, useState } from 'react';

/** A small, local 3D presenter. Speech and recognition remain in Interview. */
const PALETTES = {
  fern: { skin: 0xd6ad8e, hair: 0x253c30, clothes: 0x3b6f51 },
  ocean: { skin: 0x9d6a4d, hair: 0x222b32, clothes: 0x405e76 },
  plum: { skin: 0xe4bfaa, hair: 0x53392f, clothes: 0x745873 },
};

export default function VivStage({ speaking = false, listening = false, appearance = 'fern' }) {
  const canvasRef = useRef(null);
  const stateRef = useRef({ speaking, listening });
  const [unavailable, setUnavailable] = useState(false);
  stateRef.current = { speaking, listening };

  useEffect(() => {
    setUnavailable(false);
    let alive = true;
    let renderer;
    let observer;
    let animation;
    let resizeHandler;
    const resources = [];
    const canvas = canvasRef.current;
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    async function start() {
      try {
        const THREE = await import('three');
        if (!alive || !canvas) return;
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(35, 1, .1, 50);
        camera.position.set(0, .25, 6.6);
        camera.lookAt(0, .25, 0);
        scene.add(new THREE.HemisphereLight(0xffffff, 0x739274, 2.2));
        const light = new THREE.DirectionalLight(0xffffff, 2.3);
        light.position.set(3, 5, 5);
        scene.add(light);
        const presenter = new THREE.Group();
        scene.add(presenter);
        const head = new THREE.Group();
        head.position.y = .75;
        presenter.add(head);
        const geometry = new THREE.SphereGeometry(1, 32, 24);
        resources.push(geometry);
        function material(color, roughness = .78) {
          const value = new THREE.MeshStandardMaterial({ color, roughness });
          resources.push(value);
          return value;
        }
        const palette = PALETTES[appearance] || PALETTES.fern;
        const skin = material(palette.skin), hair = material(palette.hair), clothes = material(palette.clothes);
        const eye = material(0x1c3025), mouthMaterial = material(0x754b43);
        function sphere(parent, mat, position, scale) {
          const mesh = new THREE.Mesh(geometry, mat);
          mesh.position.set(...position);
          mesh.scale.set(...scale);
          parent.add(mesh);
          return mesh;
        }
        sphere(presenter, clothes, [0, -1.03, 0], [1.16, .9, .54]);
        sphere(presenter, skin, [0, -.25, .02], [.3, .5, .3]);
        sphere(head, hair, [0, .02, -.08], [.91, 1.07, .77]);
        sphere(head, skin, [0, -.02, .13], [.79, .92, .73]);
        sphere(head, hair, [0, .76, .18], [.79, .32, .58]);
        sphere(head, skin, [-.79, -.08, .08], [.13, .22, .14]);
        sphere(head, skin, [.79, -.08, .08], [.13, .22, .14]);
        sphere(head, eye, [-.27, .05, .805], [.065, .08, .035]);
        sphere(head, eye, [.27, .05, .805], [.065, .08, .035]);
        sphere(head, skin, [0, -.13, .85], [.09, .12, .10]);
        const mouth = sphere(head, mouthMaterial, [0, -.43, .80], [.20, .035, .025]);
        function resize() {
          if (!renderer || !canvas) return;
          const width = Math.max(1, canvas.clientWidth), height = Math.max(1, canvas.clientHeight);
          renderer.setSize(width, height, false);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          renderer.render(scene, camera);
        }
        if (typeof ResizeObserver !== 'undefined') {
          observer = new ResizeObserver(resize);
          observer.observe(canvas);
        } else { resizeHandler = resize; window.addEventListener('resize', resize); }
        resize();
        const began = performance.now();
        function render(now) {
          if (!alive) return;
          const t = (now - began) / 1000;
          if (!reducedMotion) {
            head.rotation.y = Math.sin(t * .55) * .08;
            head.rotation.x = Math.sin(t * .7) * .025;
            presenter.scale.y = 1 + Math.sin(t * 1.5) * .012;
            mouth.scale.y = stateRef.current.speaking ? .035 + Math.abs(Math.sin(t * 12)) * .095 : .035;
          }
          renderer.render(scene, camera);
          animation = requestAnimationFrame(render);
        }
        if (!reducedMotion) animation = requestAnimationFrame(render);
      } catch {
        if (alive) setUnavailable(true);
      }
    }
    start();
    return () => {
      alive = false;
      if (animation) cancelAnimationFrame(animation);
      observer?.disconnect();
      if (resizeHandler) window.removeEventListener('resize', resizeHandler);
      resources.forEach(resource => resource.dispose());
      renderer?.dispose();
    };
  }, [appearance]);

  return <div className="iv-viv-stage" aria-label="Viv interviewer">
    <canvas ref={canvasRef} className="iv-viv-canvas" aria-hidden="true" hidden={unavailable} />
    {unavailable && <div className="iv-viv-fallback" aria-hidden="true">V</div>}
    <div className="iv-viv-info"><strong>Viv</strong><span>{unavailable ? 'Visual unavailable · voice still works' : speaking ? 'Speaking' : listening ? 'Listening' : 'Ready when you are'}</span>{!speaking && !listening && <span>Turn on Read aloud to hear questions.</span>}</div>
  </div>;
}
