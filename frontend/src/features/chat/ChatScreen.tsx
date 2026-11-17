import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Terminal,
  Layers,
  ShieldCheck,
  Monitor,
  Folder,
  Trash2,
  Cpu,
  Sparkles,
  Send,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";
import { sanitize } from "@/lib/sanitize";
import { ConfirmationModal } from "@/components/ConfirmationModal";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  kind?: "text" | "plan_preview" | "clarification" | "result" | "refusal";
  plan?: any;
  options?: string[];
  status?: string;
  errors?: string[];
}

export const ChatScreen: React.FC<{ username?: string }> = ({ username = "" }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Modal state for DESTRUCTIVE plans
  const [activeModalPlan, setActiveModalPlan] = useState<any | null>(null);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsLoading(true);

    try {
      const response = await api.chat.send(trimmed);
      let assistantMsg: ChatMessage;

      if (response.kind === "plan_preview") {
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: response.summary,
          kind: "plan_preview",
          plan: response,
        };

        // If DESTRUCTIVE, automatically open confirmation modal per Section 16 & mockups
        if (response.risk === "DESTRUCTIVE") {
          setActiveModalPlan(response);
        }
      } else if (response.kind === "clarification") {
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: response.question,
          kind: "clarification",
          options: response.options,
        };
      } else if (response.kind === "refusal") {
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: response.reason,
          kind: "refusal",
        };
      } else if (response.kind === "result") {
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: response.summary,
          kind: "result",
          status: response.status,
          errors: response.errors,
        };
      } else {
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: response.text || "I have processed your request.",
          kind: "text",
        };
      }

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          content: err.message || "An error occurred connecting to ShellSense.",
          kind: "refusal",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprovePlan = async (plan: any, confirmationInput?: string) => {
    try {
      setIsLoading(true);
      const res = await api.plans.approve(plan.plan_id, plan.plan_hash, confirmationInput);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          sender: "assistant",
          content: res.summary || "Plan executed successfully.",
          kind: "result",
          status: res.status,
          errors: res.errors,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          sender: "assistant",
          content: `Execution failed: ${err.message}`,
          kind: "refusal",
        },
      ]);
    } finally {
      setIsLoading(false);
      setActiveModalPlan(null);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full flex-col justify-between max-w-4xl mx-auto">
      {/* Scrollable Viewport */}
      <div className="flex-1 overflow-y-auto pr-2 space-y-6">
        {/* Mockup Hero Card (collapses when conversation begins) */}
        {!hasMessages && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center text-center pt-8 pb-4"
          >
            {/* Glowing Logo with Orbit Ring matching mockup */}
            <div className="relative flex items-center justify-center mb-4">
              <div className="absolute -inset-4 rounded-full border border-brand-violet/30 animate-spin-slow pointer-events-none" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#1B1740] to-brand-violet text-white shadow-xl shadow-brand-indigo/25">
                <Terminal className="h-8 w-8" />
              </div>
            </div>

            <h2 className="text-3xl font-extrabold tracking-tight text-text-primary">
              ShellSense
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              Your Natural Language Operating System Assistant
            </p>

            {/* Platform Compatibility Badges */}
            <div className="mt-3 flex gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-pill border border-card-border bg-card px-3 py-1 text-xs font-medium text-text-primary shadow-sm">
                <span className="h-2 w-2 rounded-full bg-blue-500" /> Windows
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-pill border border-card-border bg-card px-3 py-1 text-xs font-medium text-text-primary shadow-sm">
                <span className="h-2 w-2 rounded-full bg-amber-500" /> Linux
              </span>
            </div>

            {/* User Greeting matching Mockup */}
            <div className="mt-8">
              <h3 className="text-2xl font-bold text-text-primary">
                {username ? `Hi ${sanitize(username)} 👋` : "Welcome to ShellSense 👋"}
              </h3>
              <p className="mt-1 text-sm text-text-secondary">
                Tell me what you want to do with your system.
              </p>
            </div>

            {/* 3 Feature Cards matching Mockup */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 w-full">
              {/* Card 1: Navy Hero card */}
              <div className="relative overflow-hidden rounded-card bg-[#1B1740] p-5 text-left text-white shadow-lg transition-transform hover:-translate-y-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white mb-3">
                  <Terminal className="h-5 w-5" />
                </div>
                <div className="font-bold text-base">Run in Plain English</div>
                <div className="mt-1 text-xs text-white/70">
                  Get system info, manage files, control processes and more.
                </div>
                <div className="absolute -bottom-6 -right-6 h-24 w-24 rounded-full bg-brand-violet/20 blur-xl pointer-events-none" />
              </div>

              {/* Card 2: Background Tasks */}
              <div className="rounded-card border border-card-border bg-card p-5 text-left shadow-card transition-transform hover:-translate-y-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-indigo/10 text-brand-indigo mb-3">
                  <Layers className="h-5 w-5" />
                </div>
                <div className="font-bold text-base text-text-primary">Background Tasks</div>
                <div className="mt-1 text-xs text-text-secondary">
                  Run long operations in the background and track progress.
                </div>
              </div>

              {/* Card 3: Safe & Confirmed */}
              <div className="rounded-card border border-card-border bg-card p-5 text-left shadow-card transition-transform hover:-translate-y-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-success/10 text-success mb-3">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div className="font-bold text-base text-text-primary">Safe & Confirmed</div>
                <div className="mt-1 text-xs text-text-secondary">
                  Sensitive actions (delete, kill, modify) always ask for your approval.
                </div>
              </div>
            </div>

            {/* Try Asking Chips matching Mockup */}
            <div className="mt-8 w-full text-left">
              <div className="text-xs font-semibold text-text-secondary mb-3">
                Try asking something like:
              </div>
              <div className="flex flex-wrap gap-2.5">
                {[
                  { text: "Show my system usage", icon: Monitor },
                  { text: "Find large files", icon: Folder },
                  { text: "Delete temporary files", icon: Trash2 },
                  { text: "List running processes", icon: Cpu },
                ].map((chip) => {
                  const Icon = chip.icon;
                  return (
                    <button
                      key={chip.text}
                      onClick={() => sendMessage(chip.text)}
                      className="flex items-center gap-2 rounded-pill border border-card-border bg-card px-4 py-2 text-xs font-medium text-text-primary shadow-sm hover:border-brand-indigo/40 hover:bg-brand-indigo/5 transition-all active:scale-95"
                    >
                      <Icon className="h-3.5 w-3.5 text-brand-indigo" />
                      <span>{chip.text}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}

        {/* Message Thread */}
        {hasMessages && (
          <div className="space-y-4 pt-4">
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-xl rounded-card p-4 text-sm ${
                    msg.sender === "user"
                      ? "bg-gradient-to-tr from-brand-indigo to-brand-violet text-white shadow-md rounded-br-sm"
                      : "bg-surface-elevated border border-card-border shadow-card text-text-primary rounded-bl-sm"
                  }`}
                >
                  {/* Text Content */}
                  <div>{sanitize(msg.content)}</div>

                  {/* Clarification Chips */}
                  {msg.kind === "clarification" && msg.options && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {msg.options.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => sendMessage(opt)}
                          className="rounded-pill bg-brand-indigo/10 px-3 py-1.5 text-xs font-medium text-brand-indigo border border-brand-indigo/20 hover:bg-brand-indigo/20 transition-colors"
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Inline Plan Preview Card (for MODIFY operations) */}
                  {msg.kind === "plan_preview" && msg.plan && (
                    <div className="mt-3 rounded-control border border-card-border bg-surface-subtle p-3.5 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-brand-indigo">
                          {msg.plan.risk} Plan Preview
                        </span>
                        <span className="font-mono text-[10px] text-text-muted">
                          {msg.plan.plan_id}
                        </span>
                      </div>
                      <div className="text-text-secondary">{msg.plan.consequences}</div>
                      {msg.plan.targets?.length > 0 && (
                        <div className="font-mono text-[11px] text-text-primary bg-black/5 dark:bg-white/5 p-2 rounded">
                          {msg.plan.targets.slice(0, 3).join(", ")}
                          {msg.plan.targets.length > 3 && ` +${msg.plan.targets.length - 3} more`}
                        </div>
                      )}
                      <div className="flex justify-end gap-2 pt-2">
                        <button
                          onClick={() => handleApprovePlan(msg.plan)}
                          className="rounded-control bg-brand-indigo px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-indigo/90"
                        >
                          Approve Plan
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Refusal Style */}
                  {msg.kind === "refusal" && (
                    <div className="mt-2 flex flex-col gap-1 text-xs text-danger font-medium">
                      <div className="flex items-center gap-1.5 font-semibold">
                        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                        {msg.content.includes("Capability") || msg.content.includes("permission") || msg.content.includes("locked")
                          ? "Permission Required"
                          : "Safety Policy Refusal"}
                      </div>
                      <div className="text-text-secondary font-normal">
                        {sanitize(msg.content)}
                      </div>
                    </div>
                  )}

                  {/* Result Style */}
                  {msg.kind === "result" && (
                    <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-success">
                      <CheckCircle2 className="h-4 w-4" />
                      Status: {msg.status}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-xs text-text-secondary italic">
                <Sparkles className="h-3.5 w-3.5 animate-spin text-brand-indigo" />
                ShellSense is planning safe operations...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input Bar matching Mockup */}
      <div className="pt-4 pb-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(inputText);
          }}
          className="relative flex items-center rounded-full border border-card-border bg-surface-elevated px-4 py-2.5 shadow-card focus-within:border-brand-indigo focus-within:ring-2 focus-within:ring-brand-indigo/20 transition-all"
        >
          <Sparkles className="h-5 w-5 text-brand-indigo mr-3 flex-shrink-0" />
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask ShellSense anything..."
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-indigo text-white shadow-sm hover:bg-brand-indigo/90 transition-all active:scale-95 disabled:opacity-50 ml-2"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>

      {/* Confirmation Modal for DESTRUCTIVE Plans */}
      {activeModalPlan && (
        <ConfirmationModal
          isOpen={true}
          title="Confirm Action"
          subtitle={`You are about to execute ${activeModalPlan.summary}`}
          consequences={activeModalPlan.consequences}
          items={activeModalPlan.targets.map((t: string) => ({ name: t }))}
          riskLevel="DESTRUCTIVE"
          expectedToken={activeModalPlan.confirmation_token}
          confirmButtonLabel={`Confirm ${activeModalPlan.confirmation_token || ""}`}
          onConfirm={() => handleApprovePlan(activeModalPlan, activeModalPlan.confirmation_token)}
          onCancel={() => setActiveModalPlan(null)}
        />
      )}
    </div>
  );
};
