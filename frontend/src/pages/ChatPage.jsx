import { useState } from 'react'
import ChatPanel from '../components/chat/ChatPanel.jsx'
import AppShell from '../components/layout/AppShell.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import ProductDetail from '../components/products/ProductDetail.jsx'
import { useConversations } from '../hooks/useConversations.js'

export default function ChatPage() {
  const chat = useConversations()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [product, setProduct] = useState(null)

  function closeSidebar() {
    setSidebarOpen(false)
  }

  function handleSelect(id) {
    chat.selectConversation(id)
    closeSidebar()
  }

  function handleNew(seed) {
    chat.startConversation(seed)
    closeSidebar()
  }

  function handleAskAboutProduct(item) {
    setProduct(null)
    chat.sendMessage(`Quero saber mais sobre ${item.shortName || item.name}.`)
  }

  if (!chat.active) return null

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onCloseSidebar={closeSidebar}
      sidebar={
        <Sidebar
          conversations={chat.conversations}
          activeId={chat.active.id}
          query={chat.query}
          onQuery={chat.setQuery}
          onSelect={handleSelect}
          onNew={() => handleNew()}
          onCategory={handleNew}
        />
      }
    >
      <ChatPanel
        conversation={chat.active}
        isDemo={chat.isDemo}
        isSending={chat.isSending}
        error={chat.error}
        onSend={chat.sendMessage}
        onOpenProduct={setProduct}
        onOpenSidebar={() => setSidebarOpen(true)}
        onDismissError={() => chat.setError('')}
        onRetry={chat.retryLast}
      />
      {product ? (
        <ProductDetail product={product} onClose={() => setProduct(null)} onAsk={handleAskAboutProduct} />
      ) : null}
    </AppShell>
  )
}
