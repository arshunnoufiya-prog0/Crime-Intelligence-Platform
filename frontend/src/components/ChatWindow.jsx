
function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
        isUser
          ? 'bg-blue-600 text-white rounded-br-none'
          : 'bg-gray-200 text-gray-900 rounded-bl-none'
      }`}>
        <p className="text-sm">{message.text}</p>

        {!isUser && message.citations && (
          <div className="mt-2 pt-2 border-t border-gray-400 text-xs opacity-80">
            <p className="font-semibold">Sources:</p>
            {message.citations.map((cite, idx) => (
              <p key={idx}>📄 {cite}</p>
            ))}
          </div>
        )}

        {!isUser && message.confidence && (
          <p className="mt-1 text-xs opacity-70">Confidence: {(message.confidence * 100).toFixed(0)}%</p>
        )}

        <p className="text-xs opacity-70 mt-2">{message.timestamp}</p>
      </div>
    </div>
  );
}

export default function ChatWindow({ chatHistory = [] }) {
  return (
    <div className="flex flex-col h-96 bg-white rounded-lg border border-gray-200 p-4 overflow-y-auto">
      {chatHistory.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No messages yet. Start typing a question.</p>
        </div>
      ) : (
        chatHistory.map(msg => <MessageBubble key={msg.id} message={msg} />)
      )}
    </div>
  );
}
