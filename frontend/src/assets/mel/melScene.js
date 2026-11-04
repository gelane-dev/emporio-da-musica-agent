/**
 * Renderização 3D da Mel (Three.js), carregada sob demanda pelo MelAvatar3D.
 *
 * - Modelo: mel_base_v04.glb (cores por vértice, sem texturas nem animações), carregado uma vez
 *   e reutilizado por todas as instâncias.
 * - Estática: renderiza só quando necessário (primeiro quadro e mudança de tamanho). Não há laço
 *   de animação, então nada se move, inclusive com prefers-reduced-motion.
 * - Fundo transparente: o círculo do avatar vem do CSS.
 */
import {
  AmbientLight,
  Box3,
  DirectionalLight,
  HemisphereLight,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import modelUrl from './mel_base_v04.glb?url'

export const MEL_MODEL_URL = modelUrl

const FIELD_OF_VIEW = 28
/** Folga ao redor da Mel dentro do círculo (1 = encostada na borda). */
const FRAME_MARGIN = 1.18

let modelPromise = null

/** Baixa e interpreta o GLB uma única vez; as instâncias recebem clones da cena. */
export function loadMelModel(loader = new GLTFLoader()) {
  if (!modelPromise) {
    modelPromise = loader.loadAsync(MEL_MODEL_URL).catch((error) => {
      modelPromise = null // permite nova tentativa em outra montagem
      throw error
    })
  }
  return modelPromise
}

/**
 * Enquadra o objeto inteiro (corpo, flor e pés) numa câmera de frente, com leve ângulo de cima.
 * Função pura para ser testada sem WebGL.
 */
export function frameObject(object, camera, margin = FRAME_MARGIN) {
  const box = new Box3().setFromObject(object)
  const size = box.getSize(new Vector3())
  const center = box.getCenter(new Vector3())
  const halfFov = (camera.fov * Math.PI) / 360
  const fitHeight = size.y / 2 / Math.tan(halfFov)
  const fitWidth = size.x / 2 / Math.tan(halfFov) / camera.aspect
  const distance = Math.max(fitHeight, fitWidth) * margin + size.z / 2
  camera.position.set(center.x, center.y + size.y * 0.06, center.z + distance)
  camera.near = distance / 100
  camera.far = distance * 10
  camera.lookAt(center)
  camera.updateProjectionMatrix()
  return { center, size, distance }
}

function addLights(scene) {
  // Luz geral suave + principal à esquerda/acima + contraluz rosada para destacar o volume.
  scene.add(new HemisphereLight(0xfff4fa, 0x3b1745, 1.6))
  scene.add(new AmbientLight(0xffffff, 0.35))
  const key = new DirectionalLight(0xffffff, 2.4)
  key.position.set(1.2, 2.2, 3)
  scene.add(key)
  const rim = new DirectionalLight(0xff8fd0, 1.4)
  rim.position.set(-2.5, 1.5, -2)
  scene.add(rim)
}

/**
 * Cria a visualização dentro de `container`. Devolve `{ resize, dispose }`.
 * Lança erro se o WebGL não estiver disponível (o componente mostra o avatar 2D).
 */
export async function createMelView(container) {
  const gltf = await loadMelModel()
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.outputColorSpace = SRGBColorSpace
  renderer.setClearColor(0x000000, 0)
  renderer.domElement.className = 'mel-avatar3d__canvas'
  renderer.domElement.setAttribute('aria-hidden', 'true')

  const scene = new Scene()
  addLights(scene)
  const model = gltf.scene.clone(true)
  scene.add(model)

  const camera = new PerspectiveCamera(FIELD_OF_VIEW, 1, 0.01, 100)
  let disposed = false

  function render() {
    if (disposed) return
    const width = Math.max(1, container.clientWidth)
    const height = Math.max(1, container.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    frameObject(model, camera)
    renderer.render(scene, camera)
  }

  container.appendChild(renderer.domElement)
  render()

  return {
    resize: render,
    dispose() {
      disposed = true
      // Geometrias e materiais são do modelo compartilhado: só o contexto desta instância é liberado.
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
    },
  }
}
