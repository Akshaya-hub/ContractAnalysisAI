import React, { useState } from "react";
import { chatWithAgent } from "../services/api";   // ✅ use chat API
import "../styles/AgentChat.css";

export default function AgentChat({ docId }) {
  const [messages, setMessages] = useState([
    { from: "agent", text: "Hi 👋 How can I help you with this contract?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMsgs = [...messages, { from: "user", text: input }];
    setMessages(newMsgs);
    setLoading(true);

    try {
      // ✅ call orchestrator LLM via /chat
      const res = await chatWithAgent(docId, input);
      setMessages([
        ...newMsgs,
        { from: "agent", text: res.answer || "🤖 No response from AI." },
      ]);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages([
        ...newMsgs,
        { from: "agent", text: "⚠️ Error contacting AI backend." },
      ]);
    }

    setInput("");
    setLoading(false);
  };

  return (
    <div className="agent-chat">
      <div className="chat-box">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.from}`}>
            {msg.text}
          </div>
        ))}
        {loading && <div className="chat-msg agent">⏳ Thinking...</div>}
      </div>
      <div className="chat-input">
        <input
          type="text"
          placeholder="Ask something..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
