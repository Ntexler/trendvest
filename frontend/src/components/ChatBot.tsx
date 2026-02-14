"use client";
import { useState, useRef, useEffect } from "react";
import { useI18n } from "@/i18n/context";
import { askAI, getChatRemaining } from "@/lib/api";
import { MessageCircle, X, Send, Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  context?: string;
}

export default function ChatBot({ context }: Props) {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [remaining, setRemaining] = useState(3);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatRemaining()
      .then((d) => setRemaining(d.remaining))
      .catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await askAI(text, locale, context);
      const assistantMsg: Message = { role: "assistant", content: res.answer };
      setMessages((prev) => [...prev, assistantMsg]);
      setRemaining(res.questions_remaining);
      setSuggestions(res.suggested_questions);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: e.message || "Error" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 md:bottom-6 end-4 z-40 w-14 h-14 bg-cyan-500 hover:bg-cyan-600 rounded-full shadow-lg shadow-cyan-500/30 flex items-center justify-center transition"
      >
        <MessageCircle className="w-6 h-6 text-white" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-20 md:bottom-6 end-4 z-40 w-[calc(100%-2rem)] md:w-96 max-h-[70vh] bg-[#111827] border border-[#334155] rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#334155]">
        <div>
          <h3 className="font-semibold text-white">{t("chat.title")}</h3>
          <p className="text-xs text-[#94a3b8]">
            {remaining} {t("chat.remaining")}
          </p>
        </div>
        <button onClick={() => setOpen(false)} className="p-1 rounded hover:bg-[#1e293b]">
          <X className="w-5 h-5 text-[#94a3b8]" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px]">
        {messages.length === 0 && (
          <div className="text-center text-[#94a3b8] text-sm py-4">
            {locale === "he" ? "שלום! שאל אותי שאלה על שוק ההון" : "Hi! Ask me a question about the stock market"}
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl p-3 text-sm ${
              msg.role === "user"
                ? "bg-cyan-500 text-white ms-auto rounded-br-sm"
                : "bg-[#1e293b] text-[#e2e8f0] me-auto rounded-bl-sm"
            }`}
          >
            <div className="whitespace-pre-wrap">{msg.content}</div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-2 items-center text-[#94a3b8]">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">
              {locale === "he" ? "חושב..." : "Thinking..."}
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions */}
      {suggestions.length > 0 && !loading && (
        <div className="px-4 pb-2 flex gap-2 overflow-x-auto">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => sendMessage(s)}
              className="whitespace-nowrap text-xs px-3 py-1.5 bg-[#1e293b] hover:bg-[#334155] text-cyan-400 rounded-full transition"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-[#334155]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder={t("chat.placeholder")}
            className="flex-1 px-3 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-white text-sm placeholder-[#94a3b8] focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="p-2 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 rounded-lg transition"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
