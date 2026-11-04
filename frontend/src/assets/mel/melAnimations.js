/**
 * Catálogo e utilitários das animações da mascote Mel.
 *
 * Cada conversa do atendimento seleciona uma entre 5 animações musicais distintas,
 * garantindo que a conversa seguinte não repita a mesma animação imediatamente.
 */

export const MEL_ANIMATIONS = [
  {
    id: 'dancing',
    name: 'Dançando',
    label: 'Mel dançando com música',
    description: 'Balançando suavemente no ritmo com notas musicais ao redor.',
  },
  {
    id: 'ukulele',
    name: 'Tocando ukulele',
    label: 'Mel tocando ukulele',
    description: 'Segurando e tocando um pequeno ukulele com ritmo alegre.',
  },
  {
    id: 'singing',
    name: 'Cantando',
    label: 'Mel cantando',
    description: 'Movimentando a boca de forma divertida com notas musicais acima.',
  },
  {
    id: 'headphones',
    name: 'Curtindo música',
    label: 'Mel curtindo música com fones de ouvido',
    description: 'De olhos fechados com fones de ouvido, balançando a cabeça no ritmo.',
  },
  {
    id: 'surprise',
    name: 'Surpresa musical',
    label: 'Mel com surpresa musical',
    description: 'Expressão alegre de surpresa com elementos musicais surgindo.',
  },
]

export const DEFAULT_ANIMATION_ID = 'ukulele'

let lastChosenAnimationId = null

/**
 * Seleciona a próxima animação garantindo que não repita imediatamente
 * a mesma da conversa anterior.
 *
 * @param {string | null} previousId - ID da animação anterior a evitar.
 * @returns {string} ID da animação escolhida.
 */
export function selectNextAnimation(previousId = null) {
  const avoid = previousId || lastChosenAnimationId
  const pool = MEL_ANIMATIONS.filter((item) => item.id !== avoid)
  const choices = pool.length > 0 ? pool : MEL_ANIMATIONS
  const index = Math.floor(Math.random() * choices.length)
  const selected = choices[index].id
  lastChosenAnimationId = selected
  return selected
}

/**
 * Obtém os metadados de uma animação por ID.
 */
export function getAnimationMeta(id) {
  return MEL_ANIMATIONS.find((item) => item.id === id) || MEL_ANIMATIONS[0]
}

