import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { Box3, PerspectiveCamera, Vector3 } from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { describe, expect, it } from 'vitest'
import { frameObject } from '../../src/assets/mel/melScene.js'

// Os testes rodam a partir de frontend/ (npm test); no jsdom import.meta.url não é file://.
const GLB = resolve('src/assets/mel/mel_base_v04.glb')

function parse() {
  const bytes = readFileSync(GLB)
  // Cópia num ArrayBuffer do ambiente de teste: o GLTFLoader usa `instanceof ArrayBuffer`.
  const buffer = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(buffer).set(bytes)
  return new GLTFLoader().parseAsync(buffer, '')
}

describe('modelo 3D da Mel (mel_base_v04.glb)', () => {
  it('carrega com o Three.js e tem as partes da personagem, sem animações', async () => {
    const gltf = await parse()
    const names = []
    gltf.scene.traverse((node) => {
      if (node.isMesh) names.push(node.name)
    })
    expect(names.sort()).toEqual(
      ['Mel_Arm_L', 'Mel_Arm_R', 'Mel_Body', 'Mel_Eye_L_Open', 'Mel_Eye_R_Open', 'Mel_Flower', 'Mel_Foot_L', 'Mel_Foot_R'].sort(),
    )
    expect(gltf.animations).toHaveLength(0)
    // O gradiente rosa-roxo vem das cores por vértice do corpo.
    const body = gltf.scene.getObjectByName('Mel_Body')
    expect(body.geometry.getAttribute('color')).toBeTruthy()
    expect(body.material.vertexColors).toBe(true)
  })

  it('o enquadramento mostra a Mel inteira dentro do círculo do avatar', async () => {
    const gltf = await parse()
    const camera = new PerspectiveCamera(28, 1, 0.01, 100)
    frameObject(gltf.scene, camera)
    gltf.scene.updateMatrixWorld(true)

    const box = new Box3().setFromObject(gltf.scene)
    const corners = []
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z]) corners.push(new Vector3(x, y, z).project(camera))

    for (const corner of corners) {
      expect(Math.abs(corner.x)).toBeLessThan(1)
      expect(Math.abs(corner.y)).toBeLessThan(1)
    }
    // Ocupa boa parte do quadro (não fica minúscula).
    const height = Math.max(...corners.map((c) => c.y)) - Math.min(...corners.map((c) => c.y))
    expect(height).toBeGreaterThan(1.2)
  })
})
