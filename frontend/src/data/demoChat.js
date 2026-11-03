import { PRODUCTS } from './demo.js'

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function includesAny(text, words) {
  return words.some((word) => text.includes(word))
}

/**
 * Respostas locais só para construir a interface.
 * Substituídas por src/services/chatService.js quando houver API HTTP.
 */
export async function demoRespond({ message }) {
  await wait(900 + Math.random() * 500)
  const text = message.trim().toLowerCase()

  if (!text) {
    return { text: '', products: [] }
  }

  if (includesAny(text, ['strat', 'vermelh', 'player ii', 'player 2'])) {
    return {
      text: 'Claro. Que tal esta Stratocaster Player II? Design clássico, som versátil e acabamento impecável. Perfeita para diversos estilos.',
      products: [PRODUCTS.player2],
    }
  }

  if (includesAny(text, ['elite', 'american'])) {
    return {
      text: 'A American Elite Strat é uma opção mais refinada, com maple flameado e vozes bem definidas. Posso detalhar especificações ou formas de pagamento.',
      products: [PRODUCTS.elite],
    }
  }

  if (includesAny(text, ['guitarra', 'guitarras'])) {
    return {
      text: 'Temos guitarras elétricas com vozes clássicas e construção consistente. Uma sugestão em destaque é a Stratocaster Player II em Sonic Red.',
      products: [PRODUCTS.player2],
    }
  }

  if (includesAny(text, ['baixo', 'baixos', 'bass'])) {
    return {
      text: 'Para estúdio, a Player Jazz Bass entrega graves definidos e ótimo conforto. Esta é uma opção disponível agora.',
      products: [PRODUCTS.jazzbass],
    }
  }

  if (includesAny(text, ['bateria', 'baterias', 'drum'])) {
    return {
      text: 'Temos a categoria de baterias no atendimento. Me diga se você busca um kit acústico para estudo ou para palco, e eu consulto as opções do catálogo.',
      products: [],
    }
  }

  if (includesAny(text, ['teclado', 'teclados', 'piano'])) {
    return {
      text: 'Posso ajudar a escolher um teclado pelo objetivo: estudo, composição ou palco. Qual desses usos está mais próximo do que você precisa?',
      products: [],
    }
  }

  if (includesAny(text, ['pagamento', 'pix', 'parcela', 'preço', 'preco'])) {
    return {
      text: 'Consigo explicar as condições gerais de pagamento da loja e, para um instrumento específico, o valor à vista, no PIX e o parcelamento. Qual produto você tem em mente?',
      products: [],
    }
  }

  if (includesAny(text, ['garantia', 'troca', 'devol'])) {
    return {
      text: 'A loja trabalha com garantia e regras de troca descritas no manual. Se quiser, posso resumir a política ou olhar um pedido específico — sem confirmar elegibilidade por aqui.',
      products: [],
    }
  }

  if (includesAny(text, ['aberto', 'horário', 'horario', 'funcion'])) {
    return {
      text: 'Posso informar o horário de funcionamento e se a loja está aberta neste momento. Prefere o status de agora ou a grade da semana?',
      products: [],
    }
  }

  if (includesAny(text, ['pedido', 'rastreio', 'entrega'])) {
    return {
      text: 'Para consultar um pedido preciso do número e de um dado de confirmação. Qual é o código do pedido?',
      products: [],
    }
  }

  return {
    text: 'Posso ajudar com instrumentos, preços, disponibilidade, pedidos e políticas da loja. Conte um pouco mais do que você procura.',
    products: [],
  }
}
