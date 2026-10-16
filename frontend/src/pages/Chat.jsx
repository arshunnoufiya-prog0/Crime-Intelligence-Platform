import ChatWindow from '../components/ChatWindow';
import { useChat } from '../hooks/useChat';

export default function Chat({ onOpenFir }) {
  const { messages, inputValue, isLoading, error, graph, meta, warnings, setInputValue, handleSend } = useChat();

  return (
    <div className="p-6 h-screen flex flex-col">
      <h2 className="text-2xl font-bold mb-4">💬 Intelligent Crime Search</h2>

      <ChatWindow chatHistory={messages} warnings={warnings} meta={meta} onOpenFir={onOpenFir} />

      {error && (
        <div className="mt-2 text-sm text-red-700 bg-red-100 border border-red-300 rounded px-3 py-2">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="mt-2 text-sm text-gray-500 flex items-center">
          <span className="inline-block w-2 h-2 bg-gray-500 rounded-full mr-2 animate-pulse"></span>
          answering…
        </div>
      )}

      {/* Input Area */}
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          disabled={isLoading}
          placeholder="Ask about crimes, suspects, or patterns..."
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:bg-gray-100"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-medium transition"
        >
          📤 Send
        </button>
      </div>
    </div>
  );
}
