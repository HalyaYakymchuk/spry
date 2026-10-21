"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  Calendar,
  Clock,
  Users,
  PlusCircle,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Search,
  CalendarCheck,
  TrendingUp,
  Sparkles,
  FileText,
} from "lucide-react";
import { useAuth } from "react-oidc-context";
import { getApiUrl, Meeting, Agenda } from "@/lib/api";
import { AuthHeader } from "@/components/AuthHeader";
import { AgendaManager } from "@/components/AgendaManager";

export default function MeetingsPage() {
  const auth = useAuth();
  const [authTimedOut, setAuthTimedOut] = useState(false);
  const [fallbackToken, setFallbackToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored =
        localStorage.getItem("token") ||
        localStorage.getItem("fallback_token") ||
        localStorage.getItem("id_token") ||
        process.env.NEXT_PUBLIC_FALLBACK_TOKEN;
      if (stored) {
        setFallbackToken(stored);
      }
    }
  }, []);

  useEffect(() => {
    if (!auth.isLoading) {
      setAuthTimedOut(false);
      return;
    }
    const timer = setTimeout(() => {
      setAuthTimedOut(true);
    }, 1500);
    return () => clearTimeout(timer);
  }, [auth.isLoading]);

  const isAuthLoading = auth.isLoading && !authTimedOut;
  const token =
    auth.user?.id_token ||
    auth.user?.access_token ||
    fallbackToken ||
    process.env.NEXT_PUBLIC_FALLBACK_TOKEN ||
    undefined;

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Selected meeting for Agenda management
  const [selectedMeetingForAgenda, setSelectedMeetingForAgenda] =
    useState<Meeting | null>(null);

  // Left sidebar tab: "create" or "agenda"
  const [leftTab, setLeftTab] = useState<"create" | "agenda">("create");
  const [selectedMeetingIdForInlineAgenda, setSelectedMeetingIdForInlineAgenda] =
    useState<number | null>(null);

  // Form State
  const [title, setTitle] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [attendeeCount, setAttendeeCount] = useState<number>(1);
  const [formError, setFormError] = useState<string | null>(null);

  // Filter & Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "upcoming" | "past">("all");

  const fetchMeetings = useCallback(
    async (isManualRefresh = false) => {
      if (!token) {
        if (isManualRefresh) {
          setError("Please sign in to view and refresh meetings.");
        }
        setLoading(false);
        setRefreshing(false);
        return;
      }

      if (isManualRefresh) {
        setRefreshing(true);
        setError(null);
      }
      try {
        const res = await fetch(getApiUrl("/api/meetings"), {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          throw new Error(`Failed to fetch meetings: ${res.status} ${res.statusText}`);
        }
        const data: Meeting[] = await res.json();
        setMeetings(data);
        setError(null);
      } catch (err: unknown) {
        console.error("Error fetching meetings:", err);
        setError(err instanceof Error ? err.message : "Failed to load meetings from backend");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token]
  );

  useEffect(() => {
    if (isAuthLoading) return;
    if (token) {
      fetchMeetings();
    } else {
      setLoading(false);
      setMeetings([]);
    }
  }, [isAuthLoading, token, fetchMeetings]);

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    // Validate inputs
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setFormError("Meeting title is required.");
      return;
    }
    if (trimmedTitle.length > 255) {
      setFormError("Meeting title must not exceed 255 characters.");
      return;
    }
    if (!startsAt) {
      setFormError("Start date and time are required.");
      return;
    }
    if (!endsAt) {
      setFormError("End date and time are required.");
      return;
    }

    const startDate = new Date(startsAt);
    const endDate = new Date(endsAt);

    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      setFormError("Please enter valid dates.");
      return;
    }

    if (endDate < startDate) {
      setFormError("End time must be after or equal to start time.");
      return;
    }

    if (!attendeeCount || attendeeCount < 1) {
      setFormError("Attendee count must be at least 1.");
      return;
    }

    if (!token) {
      setFormError("Please sign in to schedule a meeting.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        title: trimmedTitle,
        starts_at: startDate.toISOString(),
        ends_at: endDate.toISOString(),
        attendee_count: Number(attendeeCount),
      };

      const res = await fetch(getApiUrl("/api/meetings"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        const errorDetail =
          errData?.detail?.[0]?.msg || errData?.detail || `Error ${res.status}: Failed to create meeting`;
        throw new Error(errorDetail);
      }

      const createdMeeting: Meeting = await res.json();
      setMeetings((prev) =>
        [...prev, createdMeeting].sort(
          (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
        )
      );

      // Reset form
      setTitle("");
      setStartsAt("");
      setEndsAt("");
      setAttendeeCount(1);
      setSuccessMessage(`"${createdMeeting.title}" has been successfully scheduled!`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to schedule meeting.");
    } finally {
      setSubmitting(false);
    }
  };

  // Analytics Metrics
  const metrics = useMemo(() => {
    const totalMeetings = meetings.length;
    const totalAttendees = meetings.reduce((acc, m) => acc + (m.attendee_count || 0), 0);
    const avgAttendees = totalMeetings > 0 ? (totalAttendees / totalMeetings).toFixed(1) : "0";

    const totalMinutes = meetings.reduce((acc, m) => {
      const diffMs = new Date(m.ends_at).getTime() - new Date(m.starts_at).getTime();
      return acc + Math.max(0, Math.round(diffMs / (1000 * 60)));
    }, 0);

    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    const durationFormatted = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

    return { totalMeetings, totalAttendees, avgAttendees, durationFormatted };
  }, [meetings]);

  // Format Helper
  const formatDateTimeRange = (startIso: string, endIso: string) => {
    try {
      const start = new Date(startIso);
      const end = new Date(endIso);

      const dateStr = start.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      });

      const startTimeStr = start.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      });

      const endTimeStr = end.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      });

      return { dateStr, timeStr: `${startTimeStr} - ${endTimeStr}` };
    } catch {
      return { dateStr: startIso, timeStr: endIso };
    }
  };

  const getDurationString = (startIso: string, endIso: string) => {
    try {
      const diffMinutes = Math.max(
        0,
        Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 60000)
      );
      if (diffMinutes < 60) return `${diffMinutes} mins`;
      const hrs = Math.floor(diffMinutes / 60);
      const mins = diffMinutes % 60;
      return mins > 0 ? `${hrs}h ${mins}m` : `${hrs} hr${hrs > 1 ? "s" : ""}`;
    } catch {
      return "-";
    }
  };

  const getMeetingStatus = (startIso: string, endIso: string) => {
    const now = new Date().getTime();
    const start = new Date(startIso).getTime();
    const end = new Date(endIso).getTime();

    if (now < start) return { label: "Upcoming", color: "bg-blue-100 text-blue-800 border-blue-200" };
    if (now >= start && now <= end)
      return { label: "In Progress", color: "bg-emerald-100 text-emerald-800 border-emerald-200" };
    return { label: "Past", color: "bg-slate-100 text-slate-600 border-slate-200" };
  };

  // Filtered Meetings
  const filteredMeetings = useMemo(() => {
    const now = new Date().getTime();
    return meetings.filter((meeting) => {
      const matchesSearch = meeting.title.toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchesSearch) return false;

      const end = new Date(meeting.ends_at).getTime();
      if (statusFilter === "upcoming") return end >= now;
      if (statusFilter === "past") return end < now;
      return true;
    });
  }, [meetings, searchQuery, statusFilter]);

  const inlineSelectedMeeting = useMemo(() => {
    if (!selectedMeetingIdForInlineAgenda) return undefined;
    return meetings.find((m) => m.id === selectedMeetingIdForInlineAgenda) || undefined;
  }, [meetings, selectedMeetingIdForInlineAgenda]);

  const handleAgendaUpdated = (updatedAgenda: Agenda) => {
    setMeetings((prev) =>
      prev.map((m) =>
        m.id === updatedAgenda.meeting_id ? { ...m, agenda: updatedAgenda } : m
      )
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-600 text-white p-2.5 rounded-xl shadow-sm">
              <Calendar className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900">Spry</h1>
              <p className="text-xs text-slate-500 font-medium">Meeting Analytics & Scheduler</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <AuthHeader />
            <button
              onClick={() => fetchMeetings(true)}
              disabled={refreshing || loading}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* KPI Analytics Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Meetings</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{metrics.totalMeetings}</p>
            </div>
            <div className="bg-indigo-50 text-indigo-600 p-3 rounded-xl">
              <CalendarCheck className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Attendees</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{metrics.totalAttendees}</p>
            </div>
            <div className="bg-emerald-50 text-emerald-600 p-3 rounded-xl">
              <Users className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Avg Attendees</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{metrics.avgAttendees}</p>
            </div>
            <div className="bg-amber-50 text-amber-600 p-3 rounded-xl">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Scheduled Time</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{metrics.durationFormatted}</p>
            </div>
            <div className="bg-sky-50 text-sky-600 p-3 rounded-xl">
              <Clock className="w-5 h-5" />
            </div>
          </div>
        </section>

        {/* Global Error Banner */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
              <p className="text-sm font-medium">{error}</p>
            </div>
            <button
              onClick={() => fetchMeetings(true)}
              className="text-xs underline font-semibold text-red-700 hover:text-red-900"
            >
              Try Again
            </button>
          </div>
        )}

        {/* 2-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Create Meeting Form OR Inline Agenda Selector */}
          <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm">
            {/* Tabs for Left Column */}
            <div className="flex items-center border-b border-slate-200 mb-5 gap-2">
              <button
                type="button"
                onClick={() => setLeftTab("create")}
                className={`pb-2.5 text-xs font-bold transition-colors border-b-2 flex items-center gap-1.5 ${
                  leftTab === "create"
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                <PlusCircle className="w-4 h-4" />
                New Meeting
              </button>
              <button
                type="button"
                onClick={() => {
                  setLeftTab("agenda");
                  if (!selectedMeetingIdForInlineAgenda && meetings.length > 0) {
                    setSelectedMeetingIdForInlineAgenda(meetings[0].id);
                  }
                }}
                className={`pb-2.5 text-xs font-bold transition-colors border-b-2 flex items-center gap-1.5 ${
                  leftTab === "agenda"
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                <Sparkles className="w-4 h-4" />
                Meeting Agenda
              </button>
            </div>

            {leftTab === "create" ? (
              <>
                <p className="text-xs text-slate-500 mb-6">
                  Fill in the meeting details to schedule a new session.
                </p>

                {formError && (
                  <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
                    <span>{formError}</span>
                  </div>
                )}

                {successMessage && (
                  <div className="mb-4 bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-2 rounded-lg text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
                    <span>{successMessage}</span>
                  </div>
                )}

                <form onSubmit={handleCreateMeeting} className="space-y-4">
                  <div>
                    <label htmlFor="title" className="block text-xs font-semibold text-slate-700 mb-1">
                      Meeting Title <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="title"
                      type="text"
                      required
                      maxLength={255}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g., Weekly Team Sync"
                      className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900 placeholder:text-slate-400"
                    />
                  </div>

                  <div>
                    <label htmlFor="startsAt" className="block text-xs font-semibold text-slate-700 mb-1">
                      Starts At <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="startsAt"
                      type="datetime-local"
                      required
                      value={startsAt}
                      onChange={(e) => setStartsAt(e.target.value)}
                      className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                    />
                  </div>

                  <div>
                    <label htmlFor="endsAt" className="block text-xs font-semibold text-slate-700 mb-1">
                      Ends At <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="endsAt"
                      type="datetime-local"
                      required
                      value={endsAt}
                      onChange={(e) => setEndsAt(e.target.value)}
                      className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                    />
                  </div>

                  <div>
                    <label htmlFor="attendees" className="block text-xs font-semibold text-slate-700 mb-1">
                      Attendee Count <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="attendees"
                      type="number"
                      required
                      min={1}
                      value={attendeeCount}
                      onChange={(e) => setAttendeeCount(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-full px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full mt-2 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl shadow-sm transition-colors disabled:opacity-50"
                  >
                    {submitting ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Scheduling...
                      </>
                    ) : (
                      <>
                        <PlusCircle className="w-4 h-4" />
                        Schedule Meeting
                      </>
                    )}
                  </button>
                </form>
              </>
            ) : (
              <div className="space-y-4">
                <p className="text-xs text-slate-500">
                  Select a meeting to view, paste, and manage its agenda using AI.
                </p>

                {meetings.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-4 text-center">
                    No scheduled meetings available. Create a meeting first.
                  </p>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="meeting-select" className="block text-xs font-semibold text-slate-700 mb-1">
                        Select Meeting
                      </label>
                      <select
                        id="meeting-select"
                        value={selectedMeetingIdForInlineAgenda || ""}
                        onChange={(e) =>
                          setSelectedMeetingIdForInlineAgenda(
                            Number(e.target.value) || null
                          )
                        }
                        className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                      >
                        {meetings.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.title} (
                            {new Date(m.starts_at).toLocaleDateString()})
                          </option>
                        ))}
                      </select>
                    </div>

                    {inlineSelectedMeeting && (
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedMeetingForAgenda(inlineSelectedMeeting)
                        }
                        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition-colors"
                      >
                        <Sparkles className="w-4 h-4 text-indigo-200" />
                        Open Agenda Workspace
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Meetings Display */}
          <div className="lg:col-span-8 space-y-4">
            {/* Filter and Search Bar */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col sm:flex-row gap-3 items-center justify-between">
              <div className="relative w-full sm:w-72">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search meetings by title..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-900"
                />
              </div>

              <div className="flex items-center gap-1.5 self-end sm:self-auto">
                {(["all", "upcoming", "past"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setStatusFilter(filter)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition-colors ${
                      statusFilter === filter
                        ? "bg-indigo-50 text-indigo-600 font-semibold"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* Meetings List Container */}
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900">
                  Meetings ({filteredMeetings.length})
                </h2>
              </div>

              {loading ? (
                <div className="p-8 text-center space-y-3">
                  <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mx-auto" />
                  <p className="text-xs text-slate-500 font-medium">Loading scheduled meetings...</p>
                </div>
              ) : filteredMeetings.length === 0 ? (
                <div className="p-12 text-center space-y-3">
                  <div className="bg-slate-100 text-slate-400 w-12 h-12 rounded-2xl flex items-center justify-center mx-auto">
                    <Calendar className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800">
                    {!token && !isAuthLoading ? "Sign in to view meetings" : "No meetings found"}
                  </h3>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    {!token && !isAuthLoading
                      ? "Please sign in using the button in the top right to access and manage your meetings."
                      : searchQuery || statusFilter !== "all"
                      ? "No meetings match your search or filter criteria."
                      : "No meetings have been scheduled yet. Create your first meeting using the form on the left."}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {filteredMeetings.map((meeting) => {
                    const status = getMeetingStatus(meeting.starts_at, meeting.ends_at);
                    const { dateStr, timeStr } = formatDateTimeRange(
                      meeting.starts_at,
                      meeting.ends_at
                    );
                    const duration = getDurationString(meeting.starts_at, meeting.ends_at);
                    const hasAgenda = !!meeting.agenda;
                    const isAiAugmented = !!meeting.agenda?.ai_suggestion;

                    return (
                      <div
                        key={meeting.id}
                        className="p-5 hover:bg-slate-50/70 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                      >
                        <div className="space-y-1.5 flex-1">
                          <div className="flex items-center gap-2.5">
                            <h4 className="text-sm font-semibold text-slate-900">
                              {meeting.title}
                            </h4>
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold border ${status.color}`}
                            >
                              {status.label}
                            </span>
                            {hasAgenda && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <FileText className="w-3 h-3 text-emerald-600" />
                                Agenda ({meeting.agenda?.items?.length || 0})
                              </span>
                            )}
                            {isAiAugmented && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-violet-50 text-violet-700 border border-violet-200">
                                <Sparkles className="w-2.5 h-2.5 text-violet-600" />
                                AI
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                            <span className="inline-flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-slate-400" />
                              {dateStr}
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-slate-400" />
                              {timeStr} ({duration})
                            </span>
                            <span className="inline-flex items-center gap-1.5">
                              <Users className="w-3.5 h-3.5 text-slate-400" />
                              {meeting.attendee_count} {meeting.attendee_count === 1 ? "attendee" : "attendees"}
                            </span>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 self-start sm:self-center">
                          <button
                            type="button"
                            onClick={() => setSelectedMeetingForAgenda(meeting)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200/60 rounded-xl transition-colors shadow-xs"
                          >
                            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                            {hasAgenda ? "View / Edit Agenda" : "Paste Agenda"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Selected Meeting Agenda Workspace (Modal View) */}
        {selectedMeetingForAgenda && (
          <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
            <div className="w-full max-w-5xl my-auto animate-in fade-in zoom-in-95 duration-150">
              <AgendaManager
                meeting={selectedMeetingForAgenda}
                token={token}
                onClose={() => setSelectedMeetingForAgenda(null)}
                onSaved={(updatedAgenda) => {
                  handleAgendaUpdated(updatedAgenda);
                }}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
