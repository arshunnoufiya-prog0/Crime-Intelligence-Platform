import { useState, useRef, useCallback } from 'react';

/**
 * §14.2 change 1 — SSE event handling.
 * Consumes POST /api/intel/query/ (Django proxy → RAG) as a stream and
 * handles the §12.5 event types: reasoning, token, citations, graph,
 * warning, meta, done. Unknown event types are IGNORED, never thrown on.
 * History: the last 3 turns are sent back with each question (§11.2).
 */
const QUERY_URL = '/api/intel/query/';
const HISTORY_TURNS = 3;

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [graph, setGraph] = useState(null);
  const [meta, setMeta] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const assistantRef = useRef(null);

  const askQuestion = useCallback(async (question) => {
    const token = localStorage.getItem('access_token');
    const priorTurns = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.text }));

    const assistant = {
      id: Date.now() + 1,
      role: 'assistant',
      text: '',
      reasoning: '',
      citations: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, {
      id: Date.now(), role: 'user', text: question,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }, assistant]);
    setIsLoading(true);
    setError(null);
    setWarnings([]);
    setGraph(null);
    setMeta(null);

    let buffer = '';
    const update = (patch) => {
      setMessages((prev) => prev.map((m) => (m.id === assistant.id ? { ...m, ...patch(m) } : m)));
    };

    try {
      const res = await fetch(QUERY_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ question, history: priorTurns }),
      });
      if (!res.ok) {
        let detail = `request failed (${res.status})`;
        try {
          const body = await res.json();
          if (body?.error?.code === 'CONTEXT_OVERFLOW') {
            detail = body.error.details?.suggestion || 'query too broad — narrow it';
          } else if (body?.error?.message) {
            detail = body.error.message;
          }
        } catch { /* non-JSON error body */ }
        throw new Error(detail);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let answer = '';
      let reasoning = '';
      let citations = [];

      const handleEvent = (event, data) => {
        switch (event) {
          case 'reasoning':
            reasoning += data.t || '';
            update(() => ({ text: answer, reasoning }));
            break;
          case 'token':
            answer += data.t || '';
            update(() => ({ text: answer, reasoning }));
            break;
          case 'citations':
            citations = data.citations || [];
            update(() => ({ citations }));
            break;
          case 'graph':
            setGraph(data);
            break;
          case 'warning':
            setWarnings((prev) => [...prev, data]);
            break;
          case 'meta':
            setMeta(data);
            break;
          case 'done':
            setIsLoading(false);
            break;
          case 'error':
            setError(data?.error?.message || 'upstream error');
            setIsLoading(false);
            break;
          default:
            break; // unknown event types are ignored, not thrown on (§14.2-1)
        }
      };

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          let event = 'message';
          const dataLines = [];
          for (const line of frame.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
          }
          if (!dataLines.length) continue;
          let data;
          try { data = JSON.parse(dataLines.join('\n')); } catch { continue; }
          handleEvent(event, data);
        }
      }
      setIsLoading(false);
    } catch (err) {
      setError(err.message || 'query failed');
      setIsLoading(false);
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    const q = inputValue.trim();
    if (!q || isLoading) return;
    setInputValue('');
    askQuestion(q);
  }, [inputValue, isLoading, askQuestion]);

  return {
    messages, inputValue, isLoading, error, graph, meta, warnings,
    setInputValue, handleSend,
  };
}

export default useChat;
