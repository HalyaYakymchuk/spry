"use client";

import { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  RefreshCw,
  X,
  Plus,
  Trash2,
  Calendar,
  Clock,
  User,
  CheckCircle2,
  AlertCircle,
  FileText,
  Bot,
  Info,
} from "lucide-react";
import {
  Agenda,
  AgendaItem,
  ActionItem,
  Meeting,
  fetchMeetingAgenda,
  saveMeetingAgenda,
  parseAgendaText,
} from "@/lib/api";

interface AgendaManagerProps {
  meeting: Meeting;
  token?: string;
  onClose?: () => void;
  onSaved?: (updatedAgenda: Agenda) => void;
}

export function AgendaManager({
  meeting,
  token,
  onClose,
  onSaved,
}: AgendaManagerProps) {
  // Navigation / Tab state for smaller viewports
  const [activeTab, setActiveTab] = useState<"paste" | "form">("paste");

  // Parser state
  const [pastedText, setPastedText] = useState("");
  const [isParsing, setIsParsing] = useState(false);
  const [parseStatus, setParseStatus] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseSuccessMessage, setParseSuccessMessage] = useState<string | null>(
    null
  );

  // AbortController reference
  const abortControllerRef = useRef<AbortController | null>(null);

  // Form state
  const [title, setTitle] = useState(meeting.title || "");
  const [items, setItems] = useState<AgendaItem[]>([
    { topic: "", owner: "", minutes: null },
  ]);
  const [actionItems, setActionItems] = useState<ActionItem[]>([
    { task: "", owner: "", due: "" },
  ]);

  // Suggested field keys (e.g., "title", "item-0-topic", "action-1-due")
  const [suggestedFields, setSuggestedFields] = useState<Set<string>>(
    new Set()
  );

  // AI Quality Signal metadata
  const [aiMetadata, setAiMetadata] = useState<{
    ai_suggestion: Record<string, unknown> | null;
    model: string | null;
    prompt_version: string | null;
  } | null>(null);

  // Save / Load state
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(
    null
  );

  // Fetch existing agenda on mount if present
  useEffect(() => {
    let isCancelled = false;

    async function loadAgenda() {
      try {
        setLoadingExisting(true);
        // If meeting already carries the agenda from the meetings list, use it directly
        if (meeting.agenda) {
          setTitle(meeting.agenda.title || meeting.title || "");
          if (meeting.agenda.items && meeting.agenda.items.length > 0) {
            setItems(meeting.agenda.items);
          }
          if (meeting.agenda.action_items && meeting.agenda.action_items.length > 0) {
            setActionItems(meeting.agenda.action_items);
          }
          if (meeting.agenda.ai_suggestion) {
            setAiMetadata({
              ai_suggestion: meeting.agenda.ai_suggestion,
              model: meeting.agenda.model || null,
              prompt_version: meeting.agenda.prompt_version || null,
            });
          }
          setLoadingExisting(false);
          return;
        }

        const existing = await fetchMeetingAgenda(meeting.id, token);
        if (!isCancelled && existing) {
          setTitle(existing.title || meeting.title || "");
          if (existing.items && existing.items.length > 0) {
            setItems(existing.items);
          }
          if (existing.action_items && existing.action_items.length > 0) {
            setActionItems(existing.action_items);
          }
          if (existing.ai_suggestion) {
            setAiMetadata({
              ai_suggestion: existing.ai_suggestion,
              model: existing.model || null,
              prompt_version: existing.prompt_version || null,
            });
          }
        }
      } catch (err: unknown) {
        console.warn("No existing agenda found for meeting:", err);
      } finally {
        if (!isCancelled) {
          setLoadingExisting(false);
        }
      }
    }

    loadAgenda();

    return () => {
      isCancelled = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [meeting.id, meeting.title, meeting.agenda, token]);

  // Dismiss a specific field's "suggested" badge
  const dismissBadge = (key: string) => {
    setSuggestedFields((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  };

  // Parser: handle Parse button click
  const handleParse = async () => {
    const trimmed = pastedText.trim();
    if (!trimmed) {
      setParseError("Please enter or paste meeting text to parse.");
      return;
    }

    if (trimmed.length > 10000) {
      setParseError(
        "Text exceeds the 10,000 character limit. Please shorten your input."
      );
      return;
    }

    if (!token) {
      setParseError("Cognito authentication required. Please sign in first.");
      return;
    }

    setParseError(null);
    setParseSuccessMessage(null);
    setParseStatus("Parsing agenda with Claude...");
    setIsParsing(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const data = await parseAgendaText(trimmed, token, controller.signal);
      const parsed = data.agenda;

      // 1. Populate title if non-empty
      if (parsed.title) {
        setTitle(parsed.title);
      }

      // 2. Populate agenda items (only non-null fields populated)
      const parsedItems: AgendaItem[] =
        parsed.items && parsed.items.length > 0
          ? parsed.items.map((it) => ({
              topic: it.topic || "",
              owner: it.owner || "",
              minutes: it.minutes !== null && it.minutes !== undefined ? it.minutes : null,
            }))
          : [{ topic: "", owner: "", minutes: null }];
      setItems(parsedItems);

      // 3. Populate action items (only non-null fields populated)
      const parsedActionItems: ActionItem[] =
        parsed.action_items && parsed.action_items.length > 0
          ? parsed.action_items.map((act) => ({
              task: act.task || "",
              owner: act.owner || "",
              due: act.due || "",
            }))
          : [{ task: "", owner: "", due: "" }];
      setActionItems(parsedActionItems);

      // 4. Mark prefilled non-empty fields with "suggested" badge
      const newSuggested = new Set<string>();
      if (parsed.title) {
        newSuggested.add("title");
      }
      parsedItems.forEach((it, idx) => {
        if (it.topic) newSuggested.add(`item-${idx}-topic`);
        if (it.owner) newSuggested.add(`item-${idx}-owner`);
        if (it.minutes !== null && it.minutes !== undefined) {
          newSuggested.add(`item-${idx}-minutes`);
        }
      });
      parsedActionItems.forEach((act, idx) => {
        if (act.task) newSuggested.add(`action-${idx}-task`);
        if (act.owner) newSuggested.add(`action-${idx}-owner`);
        if (act.due) newSuggested.add(`action-${idx}-due`);
      });
      setSuggestedFields(newSuggested);

      // 5. Store raw suggested agenda object for AI quality signal tracking
      setAiMetadata({
        ai_suggestion: parsed as unknown as Record<string, unknown>,
        model: data.model,
        prompt_version: data.prompt_version,
      });

      setParseStatus(null);
      setParseSuccessMessage(
        `Parsed successfully with ${data.model} (${data.prompt_version}). Suggested badges attached.`
      );

      // Switch to form tab on small screens
      setActiveTab("form");
    } catch (err: unknown) {
      if (
        (err instanceof DOMException && err.name === "AbortError") ||
        (err instanceof Error && err.name === "AbortError") ||
        abortControllerRef.current?.signal.aborted
      ) {
        setParseStatus("Parsing canceled.");
      } else if (err instanceof Error) {
        // Specific error messages from API helper
        setParseError(err.message);
        setParseStatus(null);
      } else {
        setParseError("Network failed. You can always enter the agenda manually.");
        setParseStatus(null);
      }
    } finally {
      setIsParsing(false);
      abortControllerRef.current = null;
    }
  };

  // Parser: handle Cancel button click
  const handleCancelParse = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsParsing(false);
      setParseStatus("Parsing canceled.");
    }
  };

  // Form items manipulation
  const handleAddItem = () => {
    setItems((prev) => [...prev, { topic: "", owner: "", minutes: null }]);
  };

  const handleRemoveItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
    // Clear any suggestions associated with that index
    setSuggestedFields((prev) => {
      const next = new Set<string>();
      prev.forEach((key) => {
        if (!key.startsWith(`item-${index}-`)) {
          next.add(key);
        }
      });
      return next;
    });
  };

  const handleItemChange = (
    index: number,
    field: keyof AgendaItem,
    value: string | number | null
  ) => {
    dismissBadge(`item-${index}-${field}`);
    setItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  // Form action items manipulation
  const handleAddActionItem = () => {
    setActionItems((prev) => [...prev, { task: "", owner: "", due: "" }]);
  };

  const handleRemoveActionItem = (index: number) => {
    setActionItems((prev) => prev.filter((_, i) => i !== index));
    setSuggestedFields((prev) => {
      const next = new Set<string>();
      prev.forEach((key) => {
        if (!key.startsWith(`action-${index}-`)) {
          next.add(key);
        }
      });
      return next;
    });
  };

  const handleActionItemChange = (
    index: number,
    field: keyof ActionItem,
    value: string
  ) => {
    dismissBadge(`action-${index}-${field}`);
    setActionItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  // Save agenda to backend API
  const handleSaveAgenda = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccessMessage(null);

    const validItems = items
      .filter((it) => it.topic.trim().length > 0)
      .map((it) => ({
        topic: it.topic.trim(),
        owner: it.owner?.trim() || null,
        minutes:
          it.minutes !== null && it.minutes !== undefined && !isNaN(Number(it.minutes))
            ? Number(it.minutes)
            : null,
      }));

    const validActionItems = actionItems
      .filter((act) => act.task.trim().length > 0)
      .map((act) => ({
        task: act.task.trim(),
        owner: act.owner?.trim() || null,
        due: act.due?.trim() || null,
      }));

    setIsSaving(true);
    try {
      const saved = await saveMeetingAgenda(
        meeting.id,
        {
          title: title.trim() || null,
          items: validItems,
          action_items: validActionItems,
          ai_suggestion: aiMetadata?.ai_suggestion || null,
          model: aiMetadata?.model || null,
          prompt_version: aiMetadata?.prompt_version || null,
        },
        token
      );

      setSaveSuccessMessage("Agenda saved successfully!");
      if (onSaved) {
        onSaved(saved);
      }
      setTimeout(() => setSaveSuccessMessage(null), 4000);
    } catch (err: unknown) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save agenda to backend."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const charCount = pastedText.length;
  const isOversized = charCount > 10000;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xl overflow-hidden flex flex-col max-w-6xl w-full mx-auto my-4 transition-all">
      {/* Modal / Header bar */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-500/20 text-indigo-300 p-2 rounded-xl border border-indigo-400/30">
            <Bot className="w-5 h-5 text-indigo-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold tracking-tight text-white">
                Meeting Agenda: {meeting.title}
              </h2>
              {aiMetadata && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  <Sparkles className="w-2.5 h-2.5" /> AI Augmented
                </span>
              )}
            </div>
            <p className="text-xs text-slate-300 mt-0.5 flex items-center gap-3">
              <span className="inline-flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" />
                {new Date(meeting.starts_at).toLocaleDateString()}
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-400" />
                {new Date(meeting.starts_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span className="inline-flex items-center gap-1">
                <User className="w-3 h-3 text-slate-400" />
                {meeting.attendee_count} attendees
              </span>
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Tabs navigation for mobile */}
      <div className="flex lg:hidden border-b border-slate-200 bg-slate-50 px-4 pt-2">
        <button
          onClick={() => setActiveTab("paste")}
          className={`flex-1 py-2 text-xs font-semibold text-center border-b-2 transition-colors ${
            activeTab === "paste"
              ? "border-indigo-600 text-indigo-600 bg-white rounded-t-lg"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          1. Paste & Parse
        </button>
        <button
          onClick={() => setActiveTab("form")}
          className={`flex-1 py-2 text-xs font-semibold text-center border-b-2 transition-colors ${
            activeTab === "form"
              ? "border-indigo-600 text-indigo-600 bg-white rounded-t-lg"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          2. Check & Save Agenda ({items.length} items)
        </button>
      </div>

      {/* Main Body: Two Columns side-by-side on lg */}
      <div className="p-6 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Paste, Check, Parse Input */}
        <section
          className={`lg:col-span-5 space-y-4 ${
            activeTab !== "paste" ? "hidden lg:block" : "block"
          }`}
        >
          <div className="bg-slate-50 border border-slate-200/90 rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Paste Raw Agenda / Notes
                </h3>
              </div>
              <span
                className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                  isOversized
                    ? "bg-red-100 text-red-700 font-bold"
                    : charCount > 8500
                    ? "bg-amber-100 text-amber-700"
                    : "bg-slate-200/80 text-slate-600"
                }`}
              >
                {charCount.toLocaleString()} / 10,000 chars
              </span>
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Paste an email invite, messy meeting notes, or draft discussion
              topics. Claude will parse topics, assignees, and due dates.
            </p>

            <div className="relative">
              <textarea
                rows={9}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                disabled={isParsing}
                placeholder="Example:
Team sync tomorrow at 11am for 45 minutes.
Topics:
- Review Q4 product roadmap (Alice, 20m)
- AWS Bedrock cost allocation (Bob, 15m)
Action items:
- Alice to update Jira tickets by Friday
- Sarah to send meeting summary tomorrow"
                className="w-full p-3.5 text-xs font-mono bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900 placeholder:text-slate-400 resize-y leading-relaxed"
              />
            </div>

            {/* Error & Status Banners */}
            {parseError && (
              <div className="bg-red-50 border border-red-200 text-red-800 p-3 rounded-xl text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-red-900">Parsing Error</p>
                  <p className="mt-0.5">{parseError}</p>
                </div>
              </div>
            )}

            {parseStatus && !parseError && (
              <div className="bg-indigo-50 border border-indigo-200 text-indigo-900 p-3 rounded-xl text-xs flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <RefreshCw className="w-4 h-4 text-indigo-600 animate-spin shrink-0" />
                  <span className="font-medium">{parseStatus}</span>
                </div>
                {isParsing && (
                  <button
                    type="button"
                    onClick={handleCancelParse}
                    className="px-2.5 py-1 text-xs font-bold text-red-600 bg-red-100 hover:bg-red-200 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                )}
              </div>
            )}

            {parseSuccessMessage && !parseError && !parseStatus && (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-3 rounded-xl text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <p className="text-emerald-800">{parseSuccessMessage}</p>
              </div>
            )}

            {/* Parse & Cancel Action Bar */}
            <div className="flex items-center gap-3 pt-1">
              <button
                type="button"
                onClick={handleParse}
                disabled={isParsing || !pastedText.trim() || isOversized}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isParsing ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Parsing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-indigo-200" />
                    Parse Agenda
                  </>
                )}
              </button>

              {isParsing && (
                <button
                  type="button"
                  onClick={handleCancelParse}
                  className="px-4 py-2.5 text-xs font-bold text-slate-700 bg-slate-200 hover:bg-slate-300 active:bg-slate-400 rounded-xl transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>

            <p className="text-[11px] text-slate-500 text-center">
              Runs in eu-north-1 via Bedrock. Read-only; won&apos;t write to database.
            </p>
          </div>
        </section>

        {/* Right Column: Check, Edit & Save Form */}
        <section
          className={`lg:col-span-7 space-y-5 ${
            activeTab !== "form" ? "hidden lg:block" : "block"
          }`}
        >
          {loadingExisting ? (
            <div className="p-12 text-center space-y-3 bg-slate-50 rounded-2xl border border-slate-200">
              <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mx-auto" />
              <p className="text-xs text-slate-500 font-medium">
                Loading saved agenda...
              </p>
            </div>
          ) : (
            <form onSubmit={handleSaveAgenda} className="space-y-6">
              {/* Form Title Banner */}
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Agenda Details
                  </h3>
                  <p className="text-xs text-slate-500">
                    Review and refine before saving to database.
                  </p>
                </div>

                {suggestedFields.size > 0 && (
                  <span className="badge inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-violet-100 text-violet-700 border border-violet-200">
                    <Sparkles className="w-3 h-3 text-violet-600" />
                    {suggestedFields.size} AI suggested fields
                  </span>
                )}
              </div>

              {saveError && (
                <div className="bg-red-50 border border-red-200 text-red-800 p-3 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
                  <span>{saveError}</span>
                </div>
              )}

              {saveSuccessMessage && (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-xl text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>{saveSuccessMessage}</span>
                </div>
              )}

              {/* Agenda Title Input */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label
                    htmlFor="agenda-title"
                    className="text-xs font-semibold text-slate-700"
                  >
                    Agenda Title
                  </label>
                  {suggestedFields.has("title") && (
                    <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                      suggested
                    </span>
                  )}
                </div>
                <input
                  id="agenda-title"
                  type="text"
                  value={title}
                  onFocus={() => dismissBadge("title")}
                  onTouchStart={() => dismissBadge("title")}
                  onChange={(e) => {
                    dismissBadge("title");
                    setTitle(e.target.value);
                  }}
                  placeholder="e.g., Weekly Team Sync"
                  className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                />
              </div>

              {/* Items Section */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <span>Discussion Topics</span>
                    <span className="text-slate-400 font-normal">
                      ({items.length})
                    </span>
                  </h4>
                  <button
                    type="button"
                    onClick={handleAddItem}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Topic
                  </button>
                </div>

                <div className="space-y-2.5">
                  {items.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50/70 border border-slate-200/80 rounded-xl space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Topic #{idx + 1}
                            </span>
                            {suggestedFields.has(`item-${idx}-topic`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={item.topic}
                            onFocus={() => dismissBadge(`item-${idx}-topic`)}
                            onTouchStart={() => dismissBadge(`item-${idx}-topic`)}
                            onChange={(e) =>
                              handleItemChange(idx, "topic", e.target.value)
                            }
                            placeholder="Topic title or description"
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>

                        {items.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveItem(idx)}
                            className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors mt-3"
                            title="Remove topic"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Presenter / Owner
                            </span>
                            {suggestedFields.has(`item-${idx}-owner`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={item.owner || ""}
                            onFocus={() => dismissBadge(`item-${idx}-owner`)}
                            onTouchStart={() => dismissBadge(`item-${idx}-owner`)}
                            onChange={(e) =>
                              handleItemChange(idx, "owner", e.target.value)
                            }
                            placeholder="Optional presenter"
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>

                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Duration (min)
                            </span>
                            {suggestedFields.has(`item-${idx}-minutes`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="number"
                            min={0}
                            value={
                              item.minutes !== null && item.minutes !== undefined
                                ? item.minutes
                                : ""
                            }
                            onFocus={() => dismissBadge(`item-${idx}-minutes`)}
                            onTouchStart={() =>
                              dismissBadge(`item-${idx}-minutes`)
                            }
                            onChange={(e) =>
                              handleItemChange(
                                idx,
                                "minutes",
                                e.target.value === ""
                                  ? null
                                  : parseInt(e.target.value) || null
                              )
                            }
                            placeholder="e.g., 15"
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action Items Section */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <span>Action Items & Follow-ups</span>
                    <span className="text-slate-400 font-normal">
                      ({actionItems.length})
                    </span>
                  </h4>
                  <button
                    type="button"
                    onClick={handleAddActionItem}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Action
                  </button>
                </div>

                <div className="space-y-2.5">
                  {actionItems.map((act, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50/70 border border-slate-200/80 rounded-xl space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Task #{idx + 1}
                            </span>
                            {suggestedFields.has(`action-${idx}-task`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={act.task}
                            onFocus={() => dismissBadge(`action-${idx}-task`)}
                            onTouchStart={() =>
                              dismissBadge(`action-${idx}-task`)
                            }
                            onChange={(e) =>
                              handleActionItemChange(idx, "task", e.target.value)
                            }
                            placeholder="Action item task description"
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>

                        {actionItems.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveActionItem(idx)}
                            className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors mt-3"
                            title="Remove action item"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Assignee / Owner
                            </span>
                            {suggestedFields.has(`action-${idx}-owner`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={act.owner || ""}
                            onFocus={() => dismissBadge(`action-${idx}-owner`)}
                            onTouchStart={() =>
                              dismissBadge(`action-${idx}-owner`)
                            }
                            onChange={(e) =>
                              handleActionItemChange(idx, "owner", e.target.value)
                            }
                            placeholder="e.g., Sarah"
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>

                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] font-semibold text-slate-500">
                              Due Date
                            </span>
                            {suggestedFields.has(`action-${idx}-due`) && (
                              <span className="badge inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-700 border border-violet-200 uppercase tracking-wider">
                                suggested
                              </span>
                            )}
                          </div>
                          <input
                            type="date"
                            value={act.due || ""}
                            onFocus={() => dismissBadge(`action-${idx}-due`)}
                            onTouchStart={() =>
                              dismissBadge(`action-${idx}-due`)
                            }
                            onChange={(e) =>
                              handleActionItemChange(idx, "due", e.target.value)
                            }
                            className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quality signal feedback banner */}
              {aiMetadata && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-600 flex items-start gap-2">
                  <Info className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
                  <p>
                    <span className="font-semibold text-slate-800">
                      Quality signal tracking active:
                    </span>{" "}
                    AI suggestion metadata ({aiMetadata.model},{" "}
                    {aiMetadata.prompt_version}) will be saved alongside your
                    corrections to serve as quality evaluation feedback.
                  </p>
                </div>
              )}

              {/* Submit Button */}
              <div className="pt-2 flex items-center justify-end gap-3">
                {onClose && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2.5 text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="submit"
                  disabled={isSaving}
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl shadow-sm transition-all disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Saving to backend...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Save Agenda
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
