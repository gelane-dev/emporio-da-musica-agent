import { describe, expect, it } from 'vitest'
import { apiBaseUrlProblem } from '../../config/apiBaseUrl.js'

describe('validação de VITE_API_BASE_URL no build', () => {
  it.each([
    ['', 'vazio: modo demonstrativo'],
    [undefined, 'ausente: modo demonstrativo'],
    ['https://emporio-da-musica-agent.onrender.com', 'backend publicado'],
    ['http://localhost:8000', 'desenvolvimento local'],
    ['http://127.0.0.1:8000', 'IP local'],
    ['http://localhost:8080', 'Docker Compose'],
  ])('aceita %s (%s)', (value) => {
    expect(apiBaseUrlProblem(value)).toBeNull()
  })

  it.each([
    ['https://SUA-URL-DO-RENDER', /placeholder/],
    ['SUA-URL-DO-RENDER', /não é uma URL válida/],
    ['emporio-da-musica-agent.onrender.com', /não é uma URL válida/],
    ['ftp://emporio.example.com', /https:\/\//],
    ['https://emporio-da-musica-agent.onrender.com/api', /sem caminho/],
  ])('recusa %s', (value, message) => {
    expect(apiBaseUrlProblem(value)).toMatch(message)
  })
})
