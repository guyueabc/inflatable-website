/**
 * InflatableModel — Three.js 3D Model Preview
 * Loads and renders GLB/GLTF models in the preview container.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const container = document.getElementById("preview-container");
if (!container) throw new Error("Preview container not found");

// ── Scene Setup ──────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf1f5f9);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(3, 2, 5);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.shadowMap.enabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
container.appendChild(renderer.domElement);

// ── Lighting ─────────────────────────────────────────────────────────────
const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
scene.add(ambientLight);

const keyLight = new THREE.DirectionalLight(0xffffff, 3);
keyLight.position.set(5, 8, 5);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
keyLight.shadow.camera.near = 0.1;
keyLight.shadow.camera.far = 50;
keyLight.shadow.camera.left = -10;
keyLight.shadow.camera.right = 10;
keyLight.shadow.camera.top = 10;
keyLight.shadow.camera.bottom = -10;
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0x6366f1, 0.8);
fillLight.position.set(-3, 2, -3);
scene.add(fillLight);

const rimLight = new THREE.DirectionalLight(0xa5b4fc, 1.2);
rimLight.position.set(0, 1, -5);
scene.add(rimLight);

// ── Ground ───────────────────────────────────────────────────────────────
const groundGeo = new THREE.PlaneGeometry(10, 10);
const groundMat = new THREE.MeshStandardMaterial({
  color: 0xe2e8f0,
  roughness: 0.8,
});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -2;
ground.receiveShadow = true;
scene.add(ground);

// ── Grid helper ──────────────────────────────────────────────────────────
const grid = new THREE.GridHelper(10, 20, 0xcbd5e1, 0xcbd5e1);
grid.position.y = -1.99;
scene.add(grid);

// ── Controls ─────────────────────────────────────────────────────────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 1.5;
controls.maxDistance = 15;
controls.maxPolarAngle = Math.PI / 1.5;
controls.target.set(0, 0, 0);
controls.update();

// ── Model loader ─────────────────────────────────────────────────────────
const loader = new GLTFLoader();
let currentModel = null;

function loadModel(url) {
  // Remove previous model
  if (currentModel) {
    scene.remove(currentModel);
    disposeModel(currentModel);
    currentModel = null;
  }

  // Clear placeholder
  const placeholder = container.querySelector(".preview-placeholder");
  if (placeholder) placeholder.remove();

  loader.load(
    url,
    (gltf) => {
      currentModel = gltf.scene;

      // Center & scale
      const box = new THREE.Box3().setFromObject(currentModel);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());

      const maxDim = Math.max(size.x, size.y, size.z);
      const scale = maxDim > 0 ? 3 / maxDim : 1;
      currentModel.scale.setScalar(scale);
      currentModel.position.set(-center.x * scale, -center.y * scale, -center.z * scale);

      // Enable shadows
      currentModel.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;
        }
      });

      scene.add(currentModel);
      controls.target.set(0, 0, 0);
      controls.update();
    },
    (progress) => {
      const pct = Math.round((progress.loaded / progress.total) * 100);
      const statusEl = document.getElementById("generate-status");
      if (statusEl && !statusEl.classList.contains("hidden")) {
        statusEl.textContent = `Loading 3D model... ${pct}%`;
      }
    },
    (error) => {
      console.error("GLTF load error:", error);
      const statusEl = document.getElementById("generate-status");
      if (statusEl) {
        statusEl.textContent = "Failed to load 3D model.";
        statusEl.style.background = "#fef2f2";
        statusEl.style.color = "#ef4444";
      }
    }
  );
}

function disposeModel(obj) {
  obj.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (Array.isArray(child.material)) {
        child.material.forEach((m) => {
          Object.values(m).forEach((v) => {
            if (v && v.isTexture) v.dispose();
          });
          m.dispose();
        });
      } else {
        Object.values(child.material).forEach((v) => {
          if (v && v.isTexture) v.dispose();
        });
        child.material.dispose();
      }
    }
  });
}

// ── Render loop ──────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

// ── Resize ───────────────────────────────────────────────────────────────
window.addEventListener("resize", () => {
  if (!container) return;
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
});

// ── Listen for model-ready event ─────────────────────────────────────────
window.addEventListener("model-ready", (e) => {
  const { modelUrl } = e.detail;
  if (modelUrl) loadModel(modelUrl);
});

// ── Export for debugging ─────────────────────────────────────────────────
window._threePreview = { scene, camera, renderer, controls, loadModel };