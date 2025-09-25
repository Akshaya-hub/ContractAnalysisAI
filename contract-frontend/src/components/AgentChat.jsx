import React, { useState } from "react";
import { getRecommendations } from "../services/api";
import "../styles/AgentChat.css";

export default function AgentChat({ docId, recommendations }) {
  const [messages, setMessages] = useState([
    { from: "agent", text: "Hi 👋 How can I help you with this contract?" },
  ]);
  const [input, setInput] = useState("");

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMsgs = [...messages, { from: "user", text: input }];
    setMessages(newMsgs);

    try {
      const rec = await getRecommendations(docId);
      setMessages([
        ...newMsgs,
        { from: "agent", text: rec.suggestion || "Here’s my recommendation." },
      ]);
    } catch (err) {
      setMessages([...newMsgs, { from: "agent", text: "Error fetching advice." }]);
    }

    setInput("");
  };

  return (
    <div className="agent-chat">
      <div className="chat-box">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.from}`}>
            {msg.text}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <input
          type="text"
          placeholder="Ask something..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}
