# Relatório dos cenários end-to-end

- Modelo: openai/gpt-oss-120b
- Data de referência: 2026-03-25T10:00
- Repetições: 2

## Repetição 1

```
  FALHA  5. Arrependimento do pedido 4 com e-mail [obrigatório]
         - tool esperada ausente (ao menos uma de: consultar_politica)
         - termo esperado ausente (ao menos um de: 7 dias)
  OK   10. Saxofone fora do catálogo
  OK   14. Respostas sem emojis
  Total: 2/3 checagens
```

### Cenário 5: Arrependimento do pedido 4 com e-mail (FALHOU)

Tools: consultar_pedido

**Cliente:** Quero me arrepender da compra do pedido 4. Meu e-mail é lucas.mendes@jmail.com.

**Mel:** Oi Lucas, tudo bem?  

Para poder analisar a sua solicitação de arrependimento, preciso saber onde a compra foi feita (online no site ou diretamente na loja) e, se for online, a data em que você recebeu o violão. Essas informações são necessárias para verificar se ainda está dentro do prazo previsto pelo nosso manual de trocas e devoluções.  

Aguardo seu retorno!

- Falha: tool esperada ausente (ao menos uma de: consultar_politica)
- Falha: termo esperado ausente (ao menos um de: 7 dias)

### Cenário 10: Saxofone fora do catálogo (passou)

Tools: buscar_produtos, listar_categorias

**Cliente:** Tem saxofone?

**Mel:** Oi! Temos **Instrumentos de Sopro (Madeiras)**, que inclui saxofone, mas no momento não há nenhum modelo disponível no nosso catálogo. Se quiser, posso mostrar outras categorias ou ajudar a encontrar um instrumento similar.

## Repetição 2

```
  FALHA  5. Arrependimento do pedido 4 com e-mail [obrigatório]
         - termo esperado ausente (ao menos um de: estimativa, estimad, previsao, previsto)
  OK   10. Saxofone fora do catálogo
  OK   14. Respostas sem emojis
  Total: 2/3 checagens
```

### Cenário 5: Arrependimento do pedido 4 com e-mail (FALHOU)

Tools: consultar_pedido, consultar_politica

**Cliente:** Quero me arrepender da compra do pedido 4. Meu e-mail é lucas.mendes@jmail.com.

**Mel:** Oi Lucas, tudo bem?  

Para podermos analisar o pedido 4 e ver a possibilidade de arrependimento, preciso confirmar duas informações:

1. Você comprou esse violão Giannini GF-3D online (pelo site) ou presencialmente na loja?  
2. Em que data você recebeu o produto (ou a data aproximada de entrega)?

Com esses dados consigo verificar se ainda está dentro do prazo de 7 dias corridos do recebimento, conforme nossa política de arrependimento.  

Aguardo sua resposta!

- Falha: termo esperado ausente (ao menos um de: estimativa, estimad, previsao, previsto)

### Cenário 10: Saxofone fora do catálogo (passou)

Tools: buscar_produtos, listar_categorias

**Cliente:** Tem saxofone?

**Mel:** Olá! No momento, não temos saxofone disponível no nosso catálogo.  

Posso te mostrar as categorias que temos em estoque, como guitarras, baixos, baterias, teclados, violões, ukuleles e outros instrumentos de sopro (madeiras e metais) que ainda não estão em estoque. Quer conferir alguma dessas categorias?
