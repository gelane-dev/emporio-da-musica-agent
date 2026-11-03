import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

// O jsdom não implementa scrollIntoView (usado pela lista de mensagens).
Element.prototype.scrollIntoView = function scrollIntoView() {}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  cleanup()
})
