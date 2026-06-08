"use client";

import { useState, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = "/api";

type Tab = "exam" | "peer" | "plan" | "guide";

interface TextbookLesson {
  title: string;
  type?: string;
}

interface TextbookUnit {
  name: string;
  lessons: TextbookLesson[];
}

interface TextbookSemester {
  name: string;
  units: TextbookUnit[];
}

interface TextbookGrade {
  grade: string;
  semesters: TextbookSemester[];
}

export default function Home() {
  // Textbook tree
  const [textbooks, setTextbooks] = useState<TextbookGrade[]>([]);
  const [expandedGrade, setExpandedGrade] = useState<string | null>(null);
  const [expandedSemester, setExpandedSemester] = useState<string | null>(null);

  // Form
  const [grade, setGrade] = useState("三年级");
  const [semester, setSemester] = useState("上");
  const [lesson, setLesson] = useState("");
  const [requirements, setRequirements] = useState("");
  const [classHours, setClassHours] = useState("2");

  // Generation
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

  // Load textbook tree
  useEffect(() => {
    fetch(`${API_URL}/textbooks`)
      .then((r) => r.json())
      .then((d) => setTextbooks(d.textbooks || []))
      .catch(() => {});
  }, []);

  // Generate
  const handleGenerate = useCallback(async () => {
    if (!lesson.trim()) { setError("请选择课题"); return; }
    setError(""); setLoading(true);
    setExamAnalysis(""); setPeerAnalysis(""); setLessonPlan(""); setTeachingGuide("");
    setRevisionHistory([]); setRevisionInput(""); setActiveTab("plan");

    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grade, lesson, requirements, class_hours: classHours, semester }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "生成失败");
      const d = await res.json();
      setExamAnalysis(d.exam_analysis || "");
      setPeerAnalysis(d.peer_analysis || "");
      setLessonPlan(d.lesson_plan || "");
      setTeachingGuide(d.teaching_guide || "");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [grade, lesson, requirements, classHours, semester]);

  // Revise
  const handleRevise = useCallback(async () => {
    if (!revisionInput.trim()) return;
    setRevising(true); setError("");
    try {
      const history = revisionHistory.map((h, i) =>
        i % 2 === 0 ? `老师: ${h}` : `系统: ${h.slice(0, 100)}...`
      ).join("\n");

      const res = await fetch(`${API_URL}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_plan: lessonPlan,
          revision_request: revisionInput,
          history,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "修改失败");
      const d = await res.json();
      setRevisionHistory((prev) => [...prev, revisionInput, "修改完成"]);
      setLessonPlan(d.lesson_plan);
      setRevisionInput("");
      setActiveTab("plan");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRevising(false);
    }
  }, [revisionInput, revisionHistory, lessonPlan]);

  // Select from tree
  const selectLesson = useCallback((g: string, s: string, l: string) => {
    setGrade(g); setSemester(s); setLesson(l);
  }, []);

  const tabContent = () => {
    switch (activeTab) {
      case "exam": return examAnalysis;
      case "peer": return peerAnalysis;
      case "plan": return lessonPlan;
      case "guide": return teachingGuide;
      default: return "";
    }
  };

  const TABS: { key: Tab; label: string; icon: string }[] = [
    { key: "exam", label: "考点分析", icon: "🎯" },
    { key: "peer", label: "同行参考", icon: "👥" },
    { key: "plan", label: "教案", icon: "📝" },
    { key: "guide", label: "辅导说明", icon: "🎓" },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-amber-200 shadow-sm shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl select-none">📖</span>
            <div>
              <h1 className="text-lg font-bold text-amber-800">LeKai教案知识库</h1>
              <p className="text-xs text-gray-400">v0.2 · 四层输出 · 对话修改</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Textbook Tree */}
        <aside className="w-64 bg-white border-r border-amber-100 overflow-y-auto shrink-0 hidden md:block">
          <div className="p-3 border-b border-amber-100 text-sm font-semibold text-amber-900">
            📚 统编版教材目录
          </div>
          <div className="p-1">
            {textbooks.map((g) => (
              <div key={g.grade}>
                <button
                  onClick={() => setExpandedGrade(expandedGrade === g.grade ? null : g.grade)}
                  className={`w-full text-left px-3 py-2 text-sm font-medium rounded transition-colors ${
                    expandedGrade === g.grade ? "bg-amber-100 text-amber-900" : "text-gray-700 hover:bg-amber-50"
                  }`}
                >
                  {expandedGrade === g.grade ? "▼" : "▶"} {g.grade}
                </button>
                {expandedGrade === g.grade &&
                  g.semesters.map((sem) => (
                    <div key={sem.name} className="ml-3">
                      <button
                        onClick={() =>
                          setExpandedSemester(
                            expandedSemester === `${g.grade}-${sem.name}` ? null : `${g.grade}-${sem.name}`
                          )
                        }
                        className={`w-full text-left px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                          expandedSemester === `${g.grade}-${sem.name}`
                            ? "bg-amber-50 text-amber-800"
                            : "text-gray-600 hover:bg-amber-50"
                        }`}
                      >
                        {expandedSemester === `${g.grade}-${sem.name}` ? "▼" : "▶"} {sem.name}
                      </button>
                      {expandedSemester === `${g.grade}-${sem.name}` &&
                        sem.units.map((unit) => (
                          <div key={unit.name} className="ml-4 mb-1">
                            <div className="text-xs text-gray-400 py-0.5 px-2">{unit.name}</div>
                            {unit.lessons.map((l) => (
                              <button
                                key={l.title}
                                onClick={() => selectLesson(g.grade, sem.name, l.title)}
                                className={`block w-full text-left text-xs px-3 py-1 rounded transition-colors ${
                                  grade === g.grade && lesson === l.title
                                    ? "bg-amber-500 text-white"
                                    : "text-gray-600 hover:bg-amber-100"
                                }`}
                              >
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
        </aside>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-amber-50">
          <div className="max-w-4xl mx-auto px-4 py-6">
            {/* Form */}
            <div className="bg-white rounded-xl shadow-sm border border-amber-100 p-5 mb-6">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                <select value={grade} onChange={(e) => setGrade(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  {["一年级","二年级","三年级","四年级","五年级","六年级"].map(g => <option key={g} value={g}>{g}</option>)}
                </select>
                <select value={semester} onChange={(e) => setSemester(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="上">上册</option><option value="下">下册</option>
                </select>
                <select value={classHours} onChange={(e) => setClassHours(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="1">1课时</option><option value="2">2课时</option><option value="3">3课时</option>
                </select>
                <input type="text" value={lesson} onChange={(e) => setLesson(e.target.value)}
                  placeholder="课题名称" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-amber-400 outline-none" />
                <button onClick={handleGenerate} disabled={loading}
                  className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 text-white font-medium px-4 py-1.5 rounded-lg text-sm transition-colors">
                  {loading ? "生成中..." : "生成"}
                </button>
              </div>
              <textarea value={requirements} onChange={(e) => setRequirements(e.target.value)}
                placeholder="教学要求（可选）：如重点修辞手法、增加小练笔..." rows={1}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-amber-400 outline-none resize-none" />
              {error && <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">{error}</div>}
            </div>

            {/* Results Tabs */}
            {(examAnalysis || peerAnalysis || lessonPlan || teachingGuide) && (
              <div className="bg-white rounded-xl shadow-sm border border-amber-100 overflow-hidden mb-6">
                <div className="flex border-b border-gray-200 overflow-x-auto">
                  {TABS.map((t) => {
                    const hasContent = (
                      (t.key === "exam" && examAnalysis) ||
                      (t.key === "peer" && peerAnalysis) ||
                      (t.key === "plan" && lessonPlan) ||
                      (t.key === "guide" && teachingGuide)
                    );
                    return (
                      <button key={t.key} onClick={() => setActiveTab(t.key)}
                        disabled={!hasContent}
                        className={`flex-1 py-2.5 text-xs font-medium transition-colors whitespace-nowrap ${
                          activeTab === t.key
                            ? "text-amber-700 border-b-2 border-amber-500 bg-amber-50"
                            : hasContent ? "text-gray-500 hover:text-gray-700" : "text-gray-300 cursor-not-allowed"
                        }`}>
                        <span className="mr-1">{t.icon}</span>{t.label}
                      </button>
                    );
                  })}
                </div>
                <div className="p-5 max-h-[60vh] overflow-y-auto">
                  <div className="prose prose-amber prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{tabContent()}</ReactMarkdown>
                  </div>
                </div>
              </div>
            )}

            {/* Revision Chat */}
            {lessonPlan && (
              <div className="bg-white rounded-xl shadow-sm border border-amber-100 p-5">
                <h3 className="text-sm font-semibold text-amber-900 mb-3">💬 对话修改</h3>
                {revisionHistory.length > 0 && (
                  <div className="mb-3 space-y-1 max-h-32 overflow-y-auto text-xs">
                    {revisionHistory.map((h, i) => (
                      <div key={i} className={`p-1.5 rounded ${i % 2 === 0 ? "bg-amber-50 text-amber-800" : "bg-gray-50 text-gray-500"}`}>
                        {i % 2 === 0 ? "✏️ " : "✅ "}{h.length > 80 ? h.slice(0, 80) + "..." : h}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <input type="text" value={revisionInput} onChange={(e) => setRevisionInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRevise()}
                    placeholder="如：第二课时增加一个小练笔环节、把导入改成宁德本地场景..."
                    className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-amber-400 outline-none" />
                  <button onClick={handleRevise} disabled={revising || !revisionInput.trim()}
                    className="bg-gray-700 hover:bg-gray-800 disabled:bg-gray-300 text-white text-sm px-4 py-1.5 rounded-lg transition-colors">
                    {revising ? "修改中..." : "修改"}
                  </button>
                </div>
              </div>
            )}

            {/* Empty */}
            {!loading && !lessonPlan && !examAnalysis && (
              <div className="text-center py-20 text-gray-400 select-none">
                <div className="text-5xl mb-4">📚</div>
                <p className="text-lg font-medium text-gray-500">左侧目录选课，点击生成</p>
                <p className="text-sm mt-1">考点分析 · 同行参考 · 教案 · 辅导说明 · 对话修改</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
