import { useState } from 'react';
import { mockChatHistory } from '../data/mockData';

export function useChat() {
  const [messages, setMessages] = useState(mockChatHistory);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = () => {
    if (!inputValue.trim()) return;

    const userMsg = {
      id: messages.length + 1,
      role: "user",
      text: inputValue,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    setTimeout(() => {
      const aiMsg = {
        id: messages.length + 2,
        role: "assistant",
        text: "This is a mock response. Real API integration coming soon.",
        citations: ["FIR/2024/001 (2024-01-15)"],
        confidence: 0.85,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsLoading(false);
    }, 1500);
  };

  return { messages, inputValue, isLoading, setInputValue, handleSend };
}

export default useChat;
