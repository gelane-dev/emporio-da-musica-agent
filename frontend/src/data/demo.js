/**
 * Dados demonstrativos da interface.
 * Separados da integração real (src/services). Não representam contrato da API.
 */

export const CATEGORIES = [
  {
    id: 'guitarras',
    label: 'Guitarras',
    prompt: 'Quero conhecer as guitarras elétricas de vocês.',
    icon: 'guitar',
  },
  {
    id: 'baixos',
    label: 'Baixos',
    prompt: 'Quais baixos vocês recomendam para estúdio?',
    icon: 'bass',
  },
  {
    id: 'baterias',
    label: 'Baterias',
    prompt: 'Vocês têm baterias acústicas disponíveis?',
    icon: 'drums',
  },
  {
    id: 'teclados',
    label: 'Teclados',
    prompt: 'Estou procurando um teclado para estudo.',
    icon: 'keys',
  },
]

export const SUGGESTIONS = [
  'Quero uma Stratocaster em vermelho',
  'Como funciona o pagamento?',
  'Qual o prazo de garantia?',
  'Vocês estão abertos agora?',
]

export const PRODUCTS = {
  player2: {
    id: 'player2',
    brand: 'Fender',
    name: 'Player II Stratocaster®',
    shortName: 'Fender Player II Stratocaster',
    finish: 'Sonic Red, Maple Fingerboard',
    mobileFinish: 'Sonic Red',
    price: 'R$ 8.499,00',
    image: '/images/strat_sonic_red.jpg',
    available: true,
    featured: true,
    highlight: 'Destaque',
    description: 'Design clássico, som versátil e acabamento impecável. Perfeita para diversos estilos.',
    specs: [
      { label: 'Corpo', value: 'Alder' },
      { label: 'Captadores', value: 'Player Series Single-Coil' },
      { label: 'Escala', value: 'Maple' },
    ],
    details: {
      series: 'American Elite Series · 2024 · #US2401847',
      rating: '4.9',
      reviews: 87,
      watermark: 'FENDER',
      features: [
        {
          title: 'Sons de alta definição',
          text: 'Voz Strat clássica com versatilidade moderna',
        },
        {
          title: 'Corpo de Alburno',
          text: 'Leve e ressonante',
        },
        {
          title: 'Sistema de Tremolo',
          text: 'Fender 2-Point Deluxe',
        },
        {
          title: 'Acabamento Premium',
          text: 'Maple flameado com verniz poliuretano',
        },
      ],
      assistantNote:
        'Essa é a Strat que você perguntou! Quer ver as especificações ou condições de pagamento?',
    },
    tone: '#c43c3c',
  },
  elite: {
    id: 'elite',
    brand: 'Fender',
    name: 'American Elite Strat',
    shortName: 'Fender American Elite Strat',
    finish: 'Aged Cherry Burst, Maple Fingerboard',
    mobileFinish: 'Aged Cherry',
    price: 'R$ 18.990,00',
    image: '/images/strat_sonic_red.jpg',
    available: true,
    featured: true,
    highlight: 'Destaque',
    description: 'Série americana com maple flameado, vozes definidas e construção premium.',
    specs: [
      { label: 'Corpo', value: 'Alder flameado' },
      { label: 'Captadores', value: '4th Generation Noiseless' },
      { label: 'Escala', value: 'Maple' },
    ],
    details: {
      series: 'American Elite Series · 2024 · #US2401847',
      rating: '4.9',
      reviews: 87,
      watermark: 'FENDER',
      features: [
        {
          title: 'Sons de alta definição',
          text: 'Voz Strat clássica com versatilidade moderna',
        },
        {
          title: 'Corpo de Alburno',
          text: 'Leve e ressonante',
        },
        {
          title: 'Sistema de Tremolo',
          text: 'Fender 2-Point Deluxe',
        },
        {
          title: 'Acabamento Premium',
          text: 'Maple flameado com verniz poliuretano',
        },
      ],
      assistantNote:
        'Essa é a Strat que você perguntou! Quer ver as especificações ou condições de pagamento?',
    },
    tone: '#8a2a22',
  },
  jazzbass: {
    id: 'jazzbass',
    brand: 'Fender',
    name: 'Player Jazz Bass',
    shortName: 'Fender Player Jazz Bass',
    finish: 'Tidepool, Maple Fingerboard',
    mobileFinish: 'Tidepool',
    price: 'R$ 7.290,00',
    image: '/images/jazz_bass.jpg',
    available: true,
    featured: false,
    highlight: 'Destaque',
    description: 'Graves definidos e conforto para estúdio ou palco.',
    specs: [
      { label: 'Corpo', value: 'Alder' },
      { label: 'Captadores', value: 'Player Series Alnico 5' },
      { label: 'Escala', value: 'Maple' },
    ],
    details: {
      series: 'Player Series · 2024 · #JB21904',
      rating: '4.8',
      reviews: 41,
      watermark: 'FENDER',
      features: [
        { title: 'Punch moderno', text: 'Médios claros para mix de estúdio' },
        { title: 'Conforto', text: 'Braço em C suave' },
        { title: 'Versatilidade', text: 'Do fingerstyle ao slap' },
        { title: 'Acabamento', text: 'Tidepool brilhante' },
      ],
      assistantNote: 'Esse baixo combina tradição e definição. Posso detalhar o parcelamento se quiser.',
    },
    tone: '#2a5f78',
  },
}

export const WELCOME_TEXT =
  'Olá! 👋 Seja bem-vindo ao Empório da Música. Como posso te ajudar hoje? Você pode me falar sobre o instrumento que procura ou explorar nossas opções.'

function at(hours, minutes) {
  const date = new Date()
  date.setHours(hours, minutes, 0, 0)
  return date.toISOString()
}

export function seedConversations() {
  const strat = PRODUCTS.player2
  return [
    {
      id: 'conv-strat',
      title: 'João Silva',
      customer: {
        name: 'João Silva',
        avatar: '/images/avatar_joao.jpg',
        unread: true,
      },
      updatedAt: at(10, 24),
      timeLabel: '10:24',
      messages: [
        {
          id: 'm1',
          role: 'assistant',
          text: 'Olá! 👋 Seja bem-vindo ao Empório da Música.\nComo posso te ajudar hoje? Você pode me falar sobre o instrumento que procura ou explorar nossas opções.',
          createdAt: at(10, 22),
        },
        {
          id: 'm2',
          role: 'user',
          text: 'Olá! Quero saber mais sobre a Fender Stratocaster Player II.',
          createdAt: at(10, 23),
        },
        {
          id: 'm3',
          role: 'assistant',
          text: 'Excelente escolha! 🎸 A Fender Player II Stratocaster combina tradição e versatilidade com acabamento premium e sonoridade clássica. Aqui está uma opção disponível:',
          products: [strat],
          createdAt: at(10, 23),
        },
        {
          id: 'm4',
          role: 'assistant',
          text: 'Gostou? Posso te contar mais sobre ela ou sugerir outros modelos que combinam com o que você busca.',
          createdAt: at(10, 24),
        },
        {
          id: 'm5',
          role: 'user',
          text: 'Gostei bastante! Vou dar uma olhada nas especificações.',
          createdAt: at(10, 24),
        },
      ],
    },
    {
      id: 'conv-maria',
      title: 'Maria Costa',
      customer: {
        name: 'Maria Costa',
        avatar: '/images/avatar_maria.jpg',
        unread: false,
      },
      updatedAt: at(9, 48),
      timeLabel: '09:48',
      messages: [
        {
          id: 'p1',
          role: 'assistant',
          text: 'Olá! 👋 Seja bem-vindo ao Empório da Música. Como posso te ajudar hoje?',
          createdAt: at(9, 40),
        },
        {
          id: 'p2',
          role: 'user',
          text: 'Vocês têm pedalboard disponível?',
          createdAt: at(9, 48),
        },
        {
          id: 'p3',
          role: 'assistant',
          text: 'Temos opções de pedalboards de alumínio aeroespacial com bag acolchoada e passa-cabos integrado. Você procura para poucos pedais compactos ou um setup maior?',
          createdAt: at(9, 48),
        },
      ],
    },
    {
      id: 'conv-lucas',
      title: 'Lucas Almeida',
      customer: {
        name: 'Lucas Almeida',
        avatar: '/images/avatar_lucas.jpg',
        unread: false,
      },
      updatedAt: at(18, 10),
      timeLabel: 'Ontem',
      messages: [
        {
          id: 'a1',
          role: 'assistant',
          text: 'Olá! 👋 Seja bem-vindo ao Empório da Música. Como posso te ajudar hoje?',
          createdAt: at(18, 8),
        },
        {
          id: 'a2',
          role: 'user',
          text: 'Qual o melhor amp para estúdio?',
          createdAt: at(18, 9),
        },
        {
          id: 'a3',
          role: 'assistant',
          text: 'Para gravação em estúdio com volume controlado, amps valvulados de baixa potência (5W a 15W) com saída atenuada ou emulada são os favoritos dos produtores.',
          createdAt: at(18, 10),
        },
      ],
    },
    {
      id: 'conv-fernanda',
      title: 'Fernanda Lima',
      customer: {
        name: 'Fernanda Lima',
        avatar: '/images/avatar_fernanda.jpg',
        unread: false,
      },
      updatedAt: at(17, 5),
      timeLabel: 'Ontem',
      messages: [
        {
          id: 'b1',
          role: 'assistant',
          text: 'Olá! Seja bem-vinda ao Empório da Música. Em que posso te ajudar?',
          createdAt: at(17, 0),
        },
        {
          id: 'b2',
          role: 'user',
          text: 'Preciso de ajuda para escolher um baixo',
          createdAt: at(17, 4),
        },
        {
          id: 'b3',
          role: 'assistant',
          text: 'Excelente! O Player Jazz Bass entrega definição excepcional nos médios e conforto incomparável com o braço em C moderno. Veja esta opção:',
          products: [PRODUCTS.jazzbass],
          createdAt: at(17, 5),
        },
      ],
    },
  ]
}

export function createConversation() {
  return {
    id: `conv-${crypto.randomUUID()}`,
    title: 'Nova conversa',
    updatedAt: new Date().toISOString(),
    messages: [
      {
        id: `msg-${crypto.randomUUID()}`,
        role: 'assistant',
        text: WELCOME_TEXT,
        createdAt: new Date().toISOString(),
      },
    ],
  }
}
