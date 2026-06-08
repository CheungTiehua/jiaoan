"use client";

import { useState, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = "/api";

type Tab = "exam" | "peer" | "plan" | "guide";

interface TextbookGrade { grade: string; semesters: { name: string; units: { name: string; lessons: { title: string; type?: string }[] }[] }[] }
interface HistoryItem { id: string; timestamp: string; grade: string; lesson: string; exam_analysis: string; peer_analysis: string }

export default function Home() {
  // Auth
  const [token, setToken] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authUser, setAuthUser] = useState("");
  const [authPass, setAuthPass] = useState("");
  const [authError, setAuthError] = useState("");

  // UI
  const [textbooks, setTextbooks] = useState<TextbookGrade[]>([]);
  const [expandedGrade, setExpandedGrade] = useState<string | null>(null);
  const [expandedSemester, setExpandedSemester] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Form
  const [grade, setGrade] = useState("三年级");
  const [semester, setSemester] = useState("上");
  const [lesson, setLesson] = useState("");
  const [requirements, setRequirements] = useState("");
  const [classHours, setClassHours] = useState("2");

  // Results
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("plan");
  const [examAnalysis, setExamAnalysis] = useState("");
  const [peerAnalysis, setPeerAnalysis] = useState("");
  const [lessonPlan, setLessonPlan] = useState("");
  const [teachingGuide, setTeachingGuide] = useState("");

  // Revision
  const [revising, setRevising] = useState(false);
  const [revisionInput, setRevisionInput] = useState("");
  const [revisionHistory, setRevisionHistory] = useState<string[]>([]);

  // Init: load token from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("lekai_token");
    if (saved) setToken(saved);
  }, []);

  // Load textbooks
  useEffect(() => {
    fetch(`${API}/textbooks`).then(r => r.json()).then(d => setTextbooks(d.textbooks || [])).catch(() => {});
  }, []);

  // Auth handlers
  const doAuth = async () => {
    setAuthError("");
    const ep = authMode === "login" ? "login" : "register";
    try {
      const res = await fetch(`${API}/${ep}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: authUser, password: authPass }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "操作失败");
      if (authMode === "login") {
        setToken(d.token);
        setUsername(authUser);
        localStorage.setItem("lekai_token", d.token);
      } else {
        setAuthMode("login");
        setAuthError("注册成功，请登录");
      }
    } catch (e: any) { setAuthError(e.message); }
  };

  const doLogout = () => {
    fetch(`${API}/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
    setToken(""); setUsername(""); localStorage.removeItem("lekai_token");
    setHistory([]); setShowHistory(false);
  };

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API}/history`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setHistory(d.history || []);
        setShowHistory(true);
      }
    } catch { }
  };

  const loadHistoryDetail = async (id: string, lesson: string) => {
    try {
      const res = await fetch(`${API}/history/${id}`);
      if (res.ok) {
        const d = await res.json();
        setLesson(lesson);
        setExamAnalysis(d.exam_analysis || "");
        setPeerAnalysis(d.peer_analysis || "");
        setLessonPlan(d.lesson_plan || "");
        setTeachingGuide(d.teaching_guide || "");
        setActiveTab("plan");
        setShowHistory(false);
      }
    } catch { }
  };

  // Generate
  const handleGenerate = useCallback(async () => {
    if (!lesson.trim()) { setError("请选择课题"); return; }
    setError(""); setLoading(true);
    setExamAnalysis(""); setPeerAnalysis(""); setLessonPlan(""); setTeachingGuide("");
    setRevisionHistory([]); setRevisionInput(""); setActiveTab("plan");
    try {
      const res = await fetch(`${API}/generate`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ grade, lesson, requirements, class_hours: classHours, semester }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "生成失败");
      const d = await res.json();
      setExamAnalysis(d.exam_analysis || "");
      setPeerAnalysis(d.peer_analysis || "");
      setLessonPlan(d.lesson_plan || "");
      setTeachingGuide(d.teaching_guide || "");
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [grade, lesson, requirements, classHours, semester, token]);

  // Revise
  const handleRevise = useCallback(async () => {
    if (!revisionInput.trim()) return;
    setRevising(true); setError("");
    try {
      const h = revisionHistory.map((h, i) => i % 2 === 0 ? `老师: ${h}` : `系统: ${h.slice(0, 100)}...`).join("\n");
      const res = await fetch(`${API}/revise`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ current_plan: lessonPlan, revision_request: revisionInput, history: h }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "修改失败");
      const d = await res.json();
      setRevisionHistory(prev => [...prev, revisionInput, "修改完成"]);
      setLessonPlan(d.lesson_plan); setRevisionInput(""); setActiveTab("plan");
    } catch (e: any) { setError(e.message); }
    finally { setRevising(false); }
  }, [revisionInput, revisionHistory, lessonPlan, token]);

  const selectLesson = useCallback((g: string, s: string, l: string) => { setGrade(g); setSemester(s); setLesson(l); }, []);

  const tabContent = () => {
    switch (activeTab) { case "exam": return examAnalysis; case "peer": return peerAnalysis; case "plan": return lessonPlan; case "guide": return teachingGuide; default: return ""; }
  };

  const TABS: { key: Tab; label: string; icon: string }[] = [
    { key: "exam", label: "考点", icon: "🎯" }, { key: "peer", label: "同行", icon: "👥" },
    { key: "plan", label: "教案", icon: "📝" }, { key: "guide", label: "辅导", icon: "🎓" },
  ];

  // ---- LOGIN PAGE ----
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-amber-50">
        <div className="bg-white rounded-xl shadow-lg border border-amber-100 p-8 w-full max-w-sm">
          <div className="text-center mb-6">
            <span className="text-4xl select-none">📖</span>
            <h1 className="text-xl font-bold text-amber-800 mt-2">LeKai教案知识库</h1>
            <p className="text-xs text-gray-400 mt-1">统编版小学语文 · 福建宁德</p>
          </div>
          <input type="text" value={authUser} onChange={e => setAuthUser(e.target.value)}
            placeholder="用户名" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-amber-400 outline-none" />
          <input type="password" value={authPass} onChange={e => setAuthPass(e.target.value)}
            onKeyDown={e => e.key === "Enter" && doAuth()}
            placeholder="密码" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-amber-400 outline-none" />
          <button onClick={doAuth} className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2 rounded-lg text-sm mb-3 transition-colors">
            {authMode === "login" ? "登录" : "注册"}
          </button>
          {authError && <div className="text-sm text-red-600 text-center mb-3">{authError}</div>}
          <button onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError(""); }}
            className="w-full text-xs text-amber-600 hover:text-amber-800">
            {authMode === "login" ? "没有账号？点击注册" : "已有账号？点击登录"}
          </button>
        </div>
      </div>
    );
  }

  // ---- MAIN APP ----
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-amber-200 shadow-sm shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl select-none">📖</span>
            <h1 className="text-base font-bold text-amber-800">LeKai</h1>
            <span className="text-xs text-gray-400 hidden sm:inline">v0.4 · 多用户</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadHistory} className="text-xs text-gray-500 hover:text-amber-700 px-2 py-1 rounded">📋 历史</button>
            <span className="text-xs text-gray-400">{username}</span>
            <button onClick={doLogout} className="text-xs text-gray-400 hover:text-red-600 px-2 py-1 rounded">退出</button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 bg-white border-r border-amber-100 overflow-y-auto shrink-0 hidden md:flex flex-col">
          {showHistory ? (
            <div className="flex-1 overflow-y-auto">
              <div className="p-3 border-b border-amber-100 flex items-center justify-between">
                <span className="text-sm font-semibold text-amber-900">📋 生成历史</span>
                <button onClick={() => setShowHistory(false)} className="text-xs text-gray-400 hover:text-gray-600">✕</button>
              </div>
              {history.length === 0 && <div className="p-4 text-xs text-gray-400 text-center">暂无记录</div>}
              {history.map(h => (
                <button key={h.id} onClick={() => loadHistoryDetail(h.id, h.lesson)}
                  className="block w-full text-left px-3 py-2 text-xs border-b border-amber-50 hover:bg-amber-50 transition-colors">
                  <div className="font-medium text-gray-700">《{h.lesson}》</div>
                  <div className="text-gray-400">{h.grade} · {h.timestamp?.slice(0, 16)}</div>
                </button>
              ))}
            </div>
          ) : (
            <>
              <div className="p-3 border-b border-amber-100 text-sm font-semibold text-amber-900">📚 教材目录</div>
              <div className="flex-1 overflow-y-auto p-1">
                {textbooks.map(g => (
                  <div key={g.grade}>
                    <button onClick={() => setExpandedGrade(expandedGrade === g.grade ? null : g.grade)}
                      className={`w-full text-left px-2 py-1.5 text-xs font-medium rounded transition-colors ${expandedGrade === g.grade ? "bg-amber-100 text-amber-900" : "text-gray-700 hover:bg-amber-50"}`}>
                      {expandedGrade === g.grade ? "▼" : "▶"} {g.grade}
                    </button>
                    {expandedGrade === g.grade && g.semesters.map(sem => (
                      <div key={sem.name} className="ml-2">
                        <button onClick={() => setExpandedSemester(expandedSemester === `${g.grade}-${sem.name}` ? null : `${g.grade}-${sem.name}`)}
                          className={`w-full text-left px-2 py-1 text-xs rounded transition-colors ${expandedSemester === `${g.grade}-${sem.name}` ? "bg-amber-50 text-amber-800" : "text-gray-600 hover:bg-amber-50"}`}>
                          {expandedSemester === `${g.grade}-${sem.name}` ? "▼" : "▶"} {sem.name}
                        </button>
                        {expandedSemester === `${g.grade}-${sem.name}` && sem.units.map(unit => (
                          <div key={unit.name} className="ml-3 mb-0.5">
                            <div className="text-xs text-gray-300 py-0.5">{unit.name}</div>
                            {unit.lessons.map(l => (
                              <button key={l.title} onClick={() => selectLesson(g.grade, sem.name, l.title)}
                                className={`block w-full text-left text-xs px-2 py-0.5 rounded transition-colors ${grade === g.grade && lesson === l.title ? "bg-amber-500 text-white" : "text-gray-600 hover:bg-amber-100"}`}>
                                {l.title}
                              </button>
                            ))}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto bg-amber-50">
          <div className="max-w-4xl mx-auto px-4 py-4">
            {/* Form */}
            <div className="bg-white rounded-xl shadow-sm border border-amber-100 p-4 mb-4">
              <div className="flex flex-wrap gap-2 mb-2">
                <select value={grade} onChange={e => setGrade(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  {["一年级","二年级","三年级","四年级","五年级","六年级"].map(g => <option key={g} value={g}>{g}</option>)}
                </select>
                <select value={semester} onChange={e => setSemester(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="上">上册</option><option value="下">下册</option>
                </select>
                <select value={classHours} onChange={e => setClassHours(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="1">1课时</option><option value="2">2课时</option><option value="3">3课时</option>
                </select>
                <input type="text" value={lesson} onChange={e => setLesson(e.target.value)} placeholder="课题" className="border border-gray-300 rounded-lg px-3 py-1 text-sm focus:ring-2 focus:ring-amber-400 outline-none w-32" />
                <button onClick={handleGenerate} disabled={loading}
                  className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 text-white font-medium px-4 py-1 rounded-lg text-sm transition-colors">
                  {loading ? "生成中..." : "生成"}
                </button>
              </div>
              <textarea value={requirements} onChange={e => setRequirements(e.target.value)} placeholder="教学要求（可选）" rows={1}
                className="w-full border border-gray-300 rounded-lg px-3 py-1 text-sm focus:ring-2 focus:ring-amber-400 outline-none resize-none" />
              {error && <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">{error}</div>}
            </div>

            {/* Results */}
            {(examAnalysis || peerAnalysis || lessonPlan || teachingGuide) && (
              <div className="bg-white rounded-xl shadow-sm border border-amber-100 overflow-hidden mb-4">
                <div className="flex border-b border-gray-200 overflow-x-auto">
                  {TABS.map(t => {
                    const has = (t.key === "exam" && examAnalysis) || (t.key === "peer" && peerAnalysis) || (t.key === "plan" && lessonPlan) || (t.key === "guide" && teachingGuide);
                    return (
                      <button key={t.key} onClick={() => setActiveTab(t.key)} disabled={!has}
                        className={`flex-1 py-2 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === t.key ? "text-amber-700 border-b-2 border-amber-500 bg-amber-50" : has ? "text-gray-500 hover:text-gray-700" : "text-gray-300 cursor-not-allowed"}`}>
                        <span className="mr-1">{t.icon}</span>{t.label}
                      </button>
                    );
                  })}
                </div>
                <div className="p-4 max-h-[55vh] overflow-y-auto">
                  <div className="prose prose-amber prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{tabContent()}</ReactMarkdown>
                  </div>
                </div>
              </div>
            )}

            {/* Revise */}
            {lessonPlan && (
              <div className="bg-white rounded-xl shadow-sm border border-amber-100 p-4">
                <h3 className="text-sm font-semibold text-amber-900 mb-2">💬 对话修改</h3>
                {revisionHistory.length > 0 && (
                  <div className="mb-2 space-y-1 max-h-24 overflow-y-auto text-xs">
                    {revisionHistory.map((h, i) => (
                      <div key={i} className={`p-1 rounded ${i % 2 === 0 ? "bg-amber-50 text-amber-800" : "bg-gray-50 text-gray-500"}`}>
                        {i % 2 === 0 ? "✏️ " : "✅ "}{h.length > 80 ? h.slice(0, 80) + "..." : h}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <input type="text" value={revisionInput} onChange={e => setRevisionInput(e.target.value)} onKeyDown={e => e.key === "Enter" && handleRevise()}
                    placeholder="如：第二课时增加小练笔、导入改成宁德场景..."
                    className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-amber-400 outline-none" />
                  <button onClick={handleRevise} disabled={revising || !revisionInput.trim()}
                    className="bg-gray-700 hover:bg-gray-800 disabled:bg-gray-300 text-white text-sm px-4 py-1.5 rounded-lg transition-colors">
                    {revising ? "..." : "修改"}
                  </button>
                </div>
              </div>
            )}

            {/* Empty */}
            {!loading && !lessonPlan && !examAnalysis && (
              <div className="text-center py-16 text-gray-400 select-none">
                <div className="text-4xl mb-3">📚</div>
                <p className="text-lg font-medium text-gray-500">左侧目录选课，点击生成</p>
                <p className="text-xs mt-1">考点 · 同行 · 教案 · 辅导 · 修改 · 历史</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
