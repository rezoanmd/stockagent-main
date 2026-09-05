"use client"

import React, { useState, useEffect, useCallback, useRef } from "react"
import axios from "axios"
import ReactMarkdown from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import {
  TrendingUp,
  TrendingDown,
  PieChart,
  Landmark,
  BookOpen,
  Zap,
  Bot,
  User,
  Plus,
  Trash2,
  Lock,
  LogOut,
  ChevronDown,
  ChevronUp,
  Database,
  Cpu,
  Layers,
  Send,
  Sparkles,
  BarChart3
} from "lucide-react"

type ToolStep = {
  tool: string
  args: Record<string, unknown>
  output_preview?: string
}

type Message = {
  role: "user" | "assistant"
  content: string
  tool_steps?: ToolStep[]
}

type ChatSession = {
  id: string
  title: string
  summary: string
  updated_at?: string
}

// Dynamically handle local testing vs production URL
const getApiBaseUrl = () => {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL
  }
  if (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
    return "http://localhost:8000"
  }
  return "https://agenticai-iarw.onrender.com"
}

const API_BASE_URL = getApiBaseUrl()

const GUEST_SESSION_KEY = "agenticai_guest_session_id"
const AUTH_TOKEN_KEY = "agenticai_auth_token"
const USERNAME_KEY = "agenticai_username"

const generateId = () => Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)

// Marquee Items
const MARQUEE_TICKERS = [
  { symbol: "SPY", name: "S&P 500 ETF", val: "$542.10", change: "+0.85%", up: true },
  { symbol: "QQQ", name: "Nasdaq 100 ETF", val: "$480.35", change: "+1.20%", up: true },
  { symbol: "NVDA", name: "NVIDIA Corp", val: "$128.50", change: "+2.45%", up: true },
  { symbol: "AAPL", name: "Apple Inc", val: "$224.20", change: "-0.30%", up: false },
  { symbol: "US10Y", name: "10Y Treasury Yield", val: "4.22%", change: "-2 bps", up: false },
  { symbol: "TLT", name: "20+ Y Treasury ETF", val: "$94.15", change: "+0.40%", up: true },
]

export default function Home() {
  // Authentication & session states
  const [token, setToken] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [chats, setChats] = useState<ChatSession[]>([])
  const [currentChatId, setCurrentChatId] = useState<string>("")
  const [currentSummary, setCurrentSummary] = useState<string>("")
  const [summaryBannerOpen, setSummaryBannerOpen] = useState(true)

  // Chat window states
  const [message, setMessage] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  // Auth Dialog state
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [authUsername, setAuthUsername] = useState("")
  const [authPassword, setAuthPassword] = useState("")
  const [authError, setAuthError] = useState("")

  // Tool trace toggle map
  const [openToolTraces, setOpenToolTraces] = useState<Record<number, boolean>>({})

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Helper to attach authorization header
  const getHeaders = useCallback((authToken = token) => {
    return authToken ? { Authorization: `Bearer ${authToken}` } : {}
  }, [token])

  const fetchUserChats = useCallback(async (authToken: string) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/chats`, {
        headers: { Authorization: `Bearer ${authToken}` }
      })
      setChats(response.data)

      if (response.data.length > 0) {
        const chatId = response.data[0].id
        setLoading(true)
        try {
          const detailResponse = await axios.get(`${API_BASE_URL}/api/chats/${chatId}`, {
            headers: { Authorization: `Bearer ${authToken}` }
          })
          const chat = detailResponse.data
          setCurrentChatId(chat.id)
          setCurrentSummary(chat.summary || "")

          const loadedMessages: Message[] = []
          if (chat.recent_messages && Array.isArray(chat.recent_messages)) {
            chat.recent_messages.forEach((m: { role: "user" | "assistant"; content: string; tool_steps?: ToolStep[] }) => {
              loadedMessages.push({
                role: m.role,
                content: m.content,
                tool_steps: m.tool_steps
              })
            })
          }
          setMessages(loadedMessages)
        } catch (err) {
          console.error("Error loading chat:", err)
        } finally {
          setLoading(false)
        }
      } else {
        const newId = generateId()
        setCurrentChatId(newId)
        setMessages([])
        setCurrentSummary("")
      }
    } catch (err: unknown) {
      console.error("Error fetching chats:", err)
      const error = err as { response?: { status: number } }
      if (error.response?.status === 401) {
        localStorage.removeItem(AUTH_TOKEN_KEY)
        localStorage.removeItem(USERNAME_KEY)
        setToken(null)
        setUsername(null)
        setChats([])
        setMessages([])
        setCurrentSummary("")
        const guestSessionId = `guest_${generateId()}`
        localStorage.setItem(GUEST_SESSION_KEY, guestSessionId)
        setCurrentChatId(guestSessionId)
      }
    }
  }, [])

  // Load Auth from Local Storage on initial render
  useEffect(() => {
    const savedToken = localStorage.getItem(AUTH_TOKEN_KEY)
    const savedUsername = localStorage.getItem(USERNAME_KEY)

    if (savedToken && savedUsername) {
      setToken(savedToken)
      setUsername(savedUsername)
      fetchUserChats(savedToken)
    } else {
      let guestSessionId = localStorage.getItem(GUEST_SESSION_KEY)
      if (!guestSessionId) {
        guestSessionId = `guest_${generateId()}`
        localStorage.setItem(GUEST_SESSION_KEY, guestSessionId)
      }
      setCurrentChatId(guestSessionId)
    }
  }, [fetchUserChats])


  const loadChat = async (chatId: string, authToken = token) => {
    if (!authToken) return
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/api/chats/${chatId}`, {
        headers: { Authorization: `Bearer ${authToken}` }
      })
      const chat = response.data
      setCurrentChatId(chat.id)
      setCurrentSummary(chat.summary || "")

      const loadedMessages: Message[] = []
      if (chat.recent_messages && Array.isArray(chat.recent_messages)) {
        chat.recent_messages.forEach((m: { role: "user" | "assistant"; content: string; tool_steps?: ToolStep[] }) => {
          loadedMessages.push({
            role: m.role,
            content: m.content,
            tool_steps: m.tool_steps
          })
        })
      }
      setMessages(loadedMessages)
    } catch (err) {
      console.error("Error loading chat:", err)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteChat = async (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!token) return
    if (!confirm("Are you sure you want to delete this chat session?")) return

    try {
      await axios.delete(`${API_BASE_URL}/api/chats/${chatId}`, {
        headers: getHeaders()
      })
      setChats(prev => prev.filter(c => c.id !== chatId))
      if (currentChatId === chatId) {
        const remaining = chats.filter(c => c.id !== chatId)
        if (remaining.length > 0) {
          loadChat(remaining[0].id)
        } else {
          startNewChat()
        }
      }
    } catch (err) {
      console.error("Error deleting chat:", err)
    }
  }

  const startNewChat = () => {
    if (token) {
      const newId = generateId()
      setCurrentChatId(newId)
      setMessages([])
      setCurrentSummary("")
    } else {
      const newGuestId = `guest_${generateId()}`
      localStorage.setItem(GUEST_SESSION_KEY, newGuestId)
      setCurrentChatId(newGuestId)
      setMessages([])
      setCurrentSummary("")
    }
  }

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError("")
    if (!authUsername || !authPassword) {
      setAuthError("Username and password are required.")
      return
    }

    try {
      const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register"
      const response = await axios.post(`${API_BASE_URL}${endpoint}`, {
        username: authUsername,
        password: authPassword
      })

      const { access_token, username: resUsername } = response.data
      localStorage.setItem(AUTH_TOKEN_KEY, access_token)
      localStorage.setItem(USERNAME_KEY, resUsername)
      setToken(access_token)
      setUsername(resUsername)
      setAuthModalOpen(false)
      setAuthUsername("")
      setAuthPassword("")

      fetchUserChats(access_token)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setAuthError(error.response?.data?.detail || "Authentication failed. Please check details.")
    }
  }

  const handleLogout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    setToken(null)
    setUsername(null)
    setChats([])
    setMessages([])
    setCurrentSummary("")
    const guestSessionId = `guest_${generateId()}`
    localStorage.setItem(GUEST_SESSION_KEY, guestSessionId)
    setCurrentChatId(guestSessionId)
  }

  const sendMessage = async (promptText?: string) => {
    const textToSend = promptText || message
    if (!textToSend.trim() || loading) return

    const userMsg: Message = { role: "user", content: textToSend }
    setMessages(prev => [...prev, userMsg])
    if (!promptText) setMessage("")
    setLoading(true)

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/chat`,
        {
          session_id: currentChatId,
          message: textToSend
        },
        { headers: getHeaders() }
      )

      const { answer, summary, tool_steps } = response.data
      const assistantMsg: Message = {
        role: "assistant",
        content: answer,
        tool_steps: tool_steps
      }

      setMessages(prev => [...prev, assistantMsg])
      if (summary) setCurrentSummary(summary)

      if (token) {
        setChats(prev => {
          const idx = prev.findIndex(c => c.id === currentChatId)
          if (idx !== -1) {
            const updated = [...prev]
            updated[idx] = { ...updated[idx], summary: summary || updated[idx].summary }
            return updated
          } else {
            return [{ id: currentChatId, title: textToSend.substring(0, 35) + "...", summary: summary || "" }, ...prev]
          }
        })
      }
    } catch (err) {
      console.error("Error sending message:", err)
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Connection Error: Could not reach backend stock research agent. Please verify backend server status."
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const toggleToolTrace = (idx: number) => {
    setOpenToolTraces(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  return (
    <div className="flex flex-col h-screen bg-[#090a10] text-slate-100 font-sans overflow-hidden">
      {/* Top Navigation Bar */}
      <header className="h-16 border-b border-white/10 bg-[#0d111c]/80 backdrop-blur-xl flex items-center justify-between px-6 z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <TrendingUp className="w-5 h-5 text-slate-950 font-bold" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-wide bg-gradient-to-r from-white via-slate-200 to-emerald-400 bg-clip-text text-transparent">
              AI Stock Research Agent
            </h1>
            <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> Live Agentic Graph
              </span>
              <span>-</span>
              <span className="text-cyan-400 flex items-center gap-1"><Database className="w-3 h-3" /> NeonDB RAG</span>
            </div>
          </div>
        </div>

        {/* System Tech Badges */}
        <div className="hidden lg:flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> LangGraph ReAct
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" /> Market RAG Pipeline
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-300 border border-blue-500/20 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> Gemini 2.5
          </span>
        </div>

        {/* User Auth Section */}
        <div className="flex items-center gap-3">
          {username ? (
            <div className="flex items-center gap-3 bg-white/5 border border-white/10 px-3 py-1.5 rounded-xl">
              <User className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-medium text-slate-200">{username}</span>
              <button
                onClick={handleLogout}
                className="text-slate-400 hover:text-red-400 transition-colors ml-1"
                title="Log out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAuthModalOpen(true)}
              className="px-3.5 py-1.5 text-xs font-medium bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-semibold rounded-xl shadow-md transition-all flex items-center gap-1.5"
            >
              <Lock className="w-3.5 h-3.5" /> Sign In / Sync DB
            </button>
          )}
        </div>
      </header>

      {/* Marquee Ticker Tape */}
      <div className="h-8 bg-slate-950/80 border-b border-white/5 flex items-center overflow-hidden z-10 shrink-0 text-xs">
        <div className="animate-marquee whitespace-nowrap flex items-center gap-8 px-4">
          {[...MARQUEE_TICKERS, ...MARQUEE_TICKERS].map((t, idx) => (
            <div key={idx} className="inline-flex items-center gap-2 font-mono text-[11px]">
              <span className="font-bold text-slate-200">{t.symbol}</span>
              <span className="text-slate-400">{t.val}</span>
              <span className={`flex items-center gap-0.5 font-semibold ${t.up ? "text-emerald-400" : "text-rose-400"}`}>
                {t.up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {t.change}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Workspace split */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Sidebar */}
        <aside className="w-72 border-r border-white/10 bg-[#0c0e17]/90 backdrop-blur-xl flex flex-col p-4 shrink-0 hidden md:flex">
          <button
            onClick={startNewChat}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 text-emerald-300 font-semibold text-xs flex items-center justify-center gap-2 hover:bg-emerald-500/30 transition-all shadow-lg"
          >
            <Plus className="w-4 h-4" /> New Research Session
          </button>

          <div className="mt-6 flex-1 flex flex-col min-h-0">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2.5 px-1 flex items-center justify-between">
              <span>Saved Chat History</span>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">{chats.length}</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
              {!token ? (
                <div className="p-3.5 rounded-xl bg-slate-900/50 border border-white/5 text-center text-xs text-slate-400">
                  <p>Guest Session Active.</p>
                  <button
                    onClick={() => setAuthModalOpen(true)}
                    className="mt-2 text-emerald-400 hover:underline font-medium text-[11px]"
                  >
                    Login to persist chats in NeonDB
                  </button>
                </div>
              ) : chats.length === 0 ? (
                <div className="p-3 text-center text-xs text-slate-400">No chat history yet.</div>
              ) : (
                chats.map(chat => (
                  <div
                    key={chat.id}
                    onClick={() => loadChat(chat.id)}
                    className={`group p-2.5 rounded-xl text-xs cursor-pointer flex items-center justify-between transition-all border ${
                      chat.id === currentChatId
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-200"
                        : "bg-slate-900/40 border-white/5 text-slate-300 hover:bg-slate-800/60"
                    }`}
                  >
                    <div className="truncate font-medium flex items-center gap-2">
                      <Bot className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span className="truncate">{chat.title}</span>
                    </div>
                    <button
                      onClick={e => handleDeleteChat(chat.id, e)}
                      className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-400 transition-opacity p-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Platform Information Card */}
          <div className="mt-auto pt-4 border-t border-white/5 text-[11px] text-slate-400 space-y-1.5">
            <div className="flex items-center justify-between">
              <span>Host Backend:</span>
              <span className="text-slate-300 font-mono">Render FastAPI</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Database:</span>
              <span className="text-emerald-400 font-mono">NeonDB PostgreSQL</span>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950/40 relative">
          {/* Running Summary Collapsible Banner */}
          {currentSummary && (
            <div className="mx-4 mt-3 bg-gradient-to-r from-emerald-950/40 via-slate-900/80 to-cyan-950/40 border border-emerald-500/20 rounded-xl p-3 text-xs text-slate-300 shrink-0 backdrop-blur-md shadow-md">
              <div
                className="flex items-center justify-between cursor-pointer font-semibold text-emerald-300 text-[11px] uppercase tracking-wider"
                onClick={() => setSummaryBannerOpen(!summaryBannerOpen)}
              >
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                  LangGraph Memory Summary
                </span>
                {summaryBannerOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </div>
              {summaryBannerOpen && (
                <p className="mt-2 leading-relaxed text-slate-300 text-[11px] border-t border-white/5 pt-2">
                  {currentSummary}
                </p>
              )}
            </div>
          )}

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="max-w-3xl mx-auto py-8 px-4 text-center space-y-8">
                <div className="space-y-3">
                  <div className="inline-flex p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shadow-xl shadow-emerald-500/10">
                    <Bot className="w-10 h-10" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                    Agentic Stock Research Platform
                  </h2>
                  <p className="text-xs text-slate-400 max-w-xl mx-auto leading-relaxed">
                    Powered by LangGraph multi-step ReAct workflows, live Yahoo & Tavily market data tools, and NeonDB vector RAG context retrieval.
                  </p>
                </div>

                {/* Preset Prompt Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                  <button
                    onClick={() => sendMessage("Analyze NVDA stock price, valuation metrics, and market news")}
                    className="glass-card p-4 rounded-2xl flex items-start gap-3 text-xs group"
                  >
                    <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 group-hover:scale-110 transition-transform">
                      <BarChart3 className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-slate-200 group-hover:text-emerald-300">NVIDIA (NVDA) Stock Deep-Dive</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">Fetches price, P/E, EPS, margins, and recent news.</div>
                    </div>
                  </button>

                  <button
                    onClick={() => sendMessage("Get top holdings, expense ratio, and sector breakdown for SPY and QQQ ETFs")}
                    className="glass-card p-4 rounded-2xl flex items-start gap-3 text-xs group"
                  >
                    <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 group-hover:scale-110 transition-transform">
                      <PieChart className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-slate-200 group-hover:text-cyan-300">ETF Portfolio Holdings</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">Analyzes SPY & QQQ top constituents and asset allocations.</div>
                    </div>
                  </button>

                  <button
                    onClick={() => sendMessage("Check US 10Y and 2Y Treasury Bond yields and tell me if the yield curve is inverted")}
                    className="glass-card p-4 rounded-2xl flex items-start gap-3 text-xs group"
                  >
                    <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-400 group-hover:scale-110 transition-transform">
                      <Landmark className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-slate-200 group-hover:text-blue-300">Bond Yields & Recessional Curve</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">Inspects 10Y, 2Y, 30Y Treasury yields & TLT ETF.</div>
                    </div>
                  </button>

                  <button
                    onClick={() => sendMessage("RAG Knowledge Search: How to perform Discounted Cash Flow (DCF) valuation and calculate intrinsic value")}
                    className="glass-card p-4 rounded-2xl flex items-start gap-3 text-xs group"
                  >
                    <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-400 group-hover:scale-110 transition-transform">
                      <BookOpen className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-slate-200 group-hover:text-purple-300">RAG DCF Valuation Knowledge</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">Queries NeonDB vector knowledge base for financial models.</div>
                    </div>
                  </button>
                </div>
              </div>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3 max-w-4xl mx-auto ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {m.role === "assistant" && (
                    <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 mt-1 shadow-md">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`space-y-2 max-w-[85%] ${m.role === "user" ? "items-end" : "items-start"}`}>
                    {/* User bubble vs Assistant bubble */}
                    <div
                      className={`p-4 rounded-2xl text-xs leading-relaxed ${
                        m.role === "user"
                          ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-slate-950 font-semibold shadow-lg shadow-emerald-500/10"
                          : "glass-card text-slate-200 shadow-xl border border-white/10"
                      }`}
                    >
                      {m.role === "user" ? (
                        <p>{m.content}</p>
                      ) : (
                        <div className="markdown-body">
                          <ReactMarkdown
                            components={{
                              code({ ref, node, className, children, ...props }: any) {
                                const match = /language-(\w+)/.exec(className || "")
                                return match ? (
                                  <SyntaxHighlighter
                                    style={oneDark as any}
                                    language={match[1]}
                                    PreTag="div"
                                  >
                                    {String(children).replace(/\n$/, "")}
                                  </SyntaxHighlighter>
                                ) : (
                                  <code className={className} {...props}>
                                    {children}
                                  </code>
                                )
                              }
                            }}
                          >
                            {m.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>

                    {/* Tool Steps Accordion for Assistant */}
                    {m.role === "assistant" && m.tool_steps && m.tool_steps.length > 0 && (
                      <div className="text-[11px] bg-slate-900/60 border border-white/5 rounded-xl p-2.5 text-slate-400 space-y-1.5 w-full">
                        <div
                          className="flex items-center justify-between cursor-pointer font-mono font-semibold text-cyan-400 hover:text-cyan-300"
                          onClick={() => toggleToolTrace(idx)}
                        >
                          <span className="flex items-center gap-1.5">
                            <Zap className="w-3.5 h-3.5 text-cyan-400" />
                            LangGraph Execution Trace ({m.tool_steps.length} Tool Calls)
                          </span>
                          {openToolTraces[idx] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </div>

                        {openToolTraces[idx] && (
                          <div className="space-y-2 border-t border-white/5 pt-2 mt-1">
                            {m.tool_steps.map((step, sIdx) => (
                              <div key={sIdx} className="bg-slate-950/80 p-2 rounded-lg border border-white/5 font-mono">
                                <div className="text-emerald-400 font-bold flex items-center justify-between">
                                  <span>Step {sIdx + 1}: {step.tool}</span>
                                  <span className="text-[10px] text-slate-300">args: {JSON.stringify(step.args)}</span>
                                </div>
                                {step.output_preview && (
                                  <div className="text-[10px] text-slate-300 mt-1 truncate">
                                    output: {step.output_preview}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {m.role === "user" && (
                    <div className="w-8 h-8 rounded-xl bg-slate-800 border border-white/10 text-slate-300 flex items-center justify-center shrink-0 mt-1">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))
            )}

            {loading && (
              <div className="flex gap-3 max-w-4xl mx-auto items-center text-xs text-slate-400">
                <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 animate-pulse">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="glass-card px-4 py-2.5 rounded-2xl flex items-center gap-2 border border-emerald-500/20">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></div>
                  <span className="font-mono text-emerald-300">LangGraph Reasoning & Fetching Market Data...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Prompt Bar Input */}
          <div className="p-4 border-t border-white/10 bg-[#0d111c]/90 backdrop-blur-xl shrink-0">
            <form
              onSubmit={e => {
                e.preventDefault()
                sendMessage()
              }}
              className="max-w-4xl mx-auto flex items-center gap-2 relative"
            >
              <div className="relative flex-1">
                <input
                  type="text"
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  placeholder="Ask about stock prices, financials, ETF holdings, bond yields, news, or RAG concepts..."
                  className="w-full py-3.5 pl-4 pr-12 text-xs rounded-2xl glass-input text-slate-100 placeholder-slate-400 focus:outline-none transition-all"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !message.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 disabled:opacity-40 text-slate-950 font-bold transition-all shadow-md"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>

      {/* Auth Modal */}
      {authModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md glass-panel p-6 rounded-3xl border border-white/10 space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-400" />
                {authMode === "login" ? "Sign In to Agent Platform" : "Create Account"}
              </h3>
              <button onClick={() => setAuthModalOpen(false)} className="text-slate-400 hover:text-white text-xs">
                X
              </button>
            </div>

            {authError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                {authError}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1.5">Username</label>
                <input
                  type="text"
                  value={authUsername}
                  onChange={e => setAuthUsername(e.target.value)}
                  className="w-full p-3 rounded-xl glass-input text-slate-100 placeholder-slate-500 focus:outline-none"
                  placeholder="Enter username"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1.5">Password</label>
                <input
                  type="password"
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                  className="w-full p-3 rounded-xl glass-input text-slate-100 placeholder-slate-500 focus:outline-none"
                  placeholder="Enter password"
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold transition-all shadow-lg"
              >
                {authMode === "login" ? "Sign In" : "Register Account"}
              </button>
            </form>

            <div className="text-center text-xs text-slate-400 pt-2 border-t border-white/5">
              {authMode === "login" ? (
                <p>
                  Don&apos;t have an account?{" "}
                  <button onClick={() => setAuthMode("register")} className="text-emerald-400 font-semibold hover:underline">
                    Register here
                  </button>
                </p>
              ) : (
                <p>
                  Already have an account?{" "}
                  <button onClick={() => setAuthMode("login")} className="text-emerald-400 font-semibold hover:underline">
                    Sign in here
                  </button>
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}