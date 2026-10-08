import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { apiClient } from "../../services/api";

const starterQuestions = [
  "What are the most important patterns?",
  "Which areas need attention?",
  "What patterns should I investigate?",
];

function errorMessage(requestError) {
  const status = requestError.response?.status;
  if (status === 429) return "AI requests are temporarily limited. Please wait a moment and try again.";
  if (status === 502 || status === 503) return "The AI service is temporarily unavailable. Your dataset analysis is still available. Please try again shortly.";
  if (status === 422) return "That question could not be processed. Check it and try again.";
  return "Unable to get an answer right now. Please try again.";
}

export default function DatasetAssistant({ dataset, onClose, explorationContext = null }) {
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retryQuestion, setRetryQuestion] = useState("");
  const messageListRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const list = messageListRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    if (explorationContext) setDraft("Explain the current exploration and summarize its key observation.");
  }, [explorationContext]);

  async function askQuestion(question, isRetry = false) {
    const cleanedQuestion = question.trim();
    if (!cleanedQuestion || loading) return;

    if (!isRetry) {
      setMessages((current) => [...current, { role: "user", content: cleanedQuestion }]);
      setDraft("");
    }

    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.post(`/datasets/${dataset.id}/ai/chat`, {
        message: cleanedQuestion,
        history: history.slice(-10),
        ...(explorationContext ? { exploration_context: explorationContext } : {}),
      });
      setMessages((current) => [...current, { role: "assistant", content: data.answer }]);
      setHistory((current) => [
        ...current,
        { role: "user", content: cleanedQuestion },
        { role: "assistant", content: data.answer },
      ].slice(-10));
      setRetryQuestion("");
    } catch (requestError) {
      setError(errorMessage(requestError));
      setRetryQuestion(cleanedQuestion);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    askQuestion(draft);
  }

  function startNewConversation() {
    setMessages([]);
    setHistory([]);
    setDraft("");
    setError("");
    setRetryQuestion("");
    inputRef.current?.focus();
  }

  return (
    <section className="assistant-panel" aria-labelledby="assistant-heading">
      <header className="assistant-header">
        <div>
          <p className="eyebrow">Dataset assistant</p>
          <h2 id="assistant-heading">AI Data Assistant</h2>
          <p className="assistant-dataset-name" title={dataset.original_filename}>{dataset.original_filename}</p>
        </div>
        <div className="assistant-header-actions">
          <button type="button" className="assistant-new-button" onClick={startNewConversation} disabled={loading}>New chat</button>
          <button type="button" className="assistant-close-button" onClick={onClose} aria-label="Close AI assistant" title="Close assistant">×</button>
        </div>
      </header>

      <div ref={messageListRef} className="assistant-messages" aria-live="polite" aria-relevant="additions text">
        {explorationContext && <p className="assistant-exploration-context" role="status">Current exploration context is attached to your next question.</p>}
        {messages.length === 0 ? (
          <div className="assistant-welcome">
            <span className="assistant-mark" aria-hidden="true">AI</span>
            <div>
              <h3>Explore your dataset using natural language.</h3>
              <p>Examples to start with. Answers use the available dataset analysis; if evidence is limited, the assistant will say so.</p>
            </div>
            <div className="assistant-starters">
              {starterQuestions.map((question) => (
                <button type="button" key={question} onClick={() => askQuestion(question)} disabled={loading}>{question}</button>
              ))}
            </div>
          </div>
        ) : messages.map((message, index) => (
          <article className={`assistant-message assistant-message-${message.role}`} key={`${message.role}-${index}`}>
            <span className="assistant-message-label">{message.role === "user" ? "You" : "Assistant"}</span>
            {message.role === "assistant" ? (
              <div className="assistant-markdown">
                <ReactMarkdown
                  skipHtml
                  components={{
                    a: ({ href, title, children }) => (
                      <a href={href} title={title} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="assistant-user-content">{message.content}</p>
            )}
          </article>
        ))}
        {loading && <div className="assistant-thinking" role="status"><span /><span /><span /> Thinking about your data</div>}
      </div>

      {error && (
        <div className="assistant-error" role="alert">
          <span>{error}</span>
          {retryQuestion && <button type="button" onClick={() => askQuestion(retryQuestion, true)} disabled={loading}>Retry</button>}
        </div>
      )}

      <form className="assistant-compose" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="assistant-question">Ask a question about this dataset</label>
        <textarea
          ref={inputRef}
          id="assistant-question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask a question about your dataset..."
          rows={2}
          maxLength={4000}
          disabled={loading}
        />
        <button type="submit" aria-label="Send question" disabled={loading || !draft.trim()} title="Send question">Send</button>
      </form>
      <p className="assistant-disclaimer">Answers are based on the available dataset summary; correlations do not establish causation.</p>
    </section>
  );
}