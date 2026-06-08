"use client";

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"];

const EXAMPLES = [
  { grade: "三年级", lesson: "富饶的西沙群岛", req: "2课时，重点修辞手法和总分总结构" },
  { grade: "三年级", lesson: "秋天的雨", req: "1课时，品味语言美，学习比喻拟人" },
  { grade: "四年级", lesson: "观潮", req: "2课时，重点朗读指导和顺序描写" },
];

export default function Home() {
  const [grade, setGrade] = useState("三年级");
  const [lesson, setLesson] = useState("");
  const [requirements, setRequirements] = useState("");
  const [classHours, setClassHours] = useState("2");
  const [semester, setSemester] = useState("上");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [lessonPlan, setLessonPlan] = useState("");
  const [teachingGuide, setTeachingGuide] = useState("");
  const [activeTab, setActiveTab] = useState<"plan" | "guide">("plan");

  const handleGenerate = useCallback(async () => {
    if (!lesson.trim()) {
      setError("请输入课题名称");
      return;
    }
    setError("");
    setLoading(true);
    setLessonPlan("");
    setTeachingGuide("");
    setActiveTab("plan");

    try {
      const res = await fetch(`${API_URL}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade,
          lesson: lesson.trim(),
          requirements: requirements.trim(),
          class_hours: classHours,
          semester,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "生成失败，请重试");
      }

      const data = await res.json();
      setLessonPlan(data.lesson_plan);
      setTeachingGuide(data.teaching_guide);
    } catch (e: any) {
      setError(e.message || "网络错误，请确认后端服务已启动");
    } finally {
      setLoading(false);
    }
  }, [grade, lesson, requirements, classHours, semester]);

  const fillExample = (ex: (typeof EXAMPLES)[0]) => {
    setGrade(ex.grade);
    setLesson(ex.lesson);
    setRequirements(ex.req);
  };

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-amber-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl select-none">📖</span>
            <div>
              <h1 className="text-xl font-bold text-amber-800">LeKai教案知识库</h1>
              <p className="text-xs text-gray-500">统编版小学语文 · 福建宁德 · 鱼渔同授</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Input */}
        <div className="bg-white rounded-xl shadow-md border border-amber-100 p-6 mb-8">
          <h2 className="text-lg font-semibold text-amber-900 mb-4">生成教案</h2>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">年级</label>
              <select
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white
                  focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
              >
                {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">学期</label>
              <select
                value={semester}
                onChange={(e) => setSemester(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white
                  focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
              >
                <option value="上">上册</option>
                <option value="下">下册</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">课时</label>
              <select
                value={classHours}
                onChange={(e) => setClassHours(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white
                  focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
              >
                <option value="1">1课时</option>
                <option value="2">2课时</option>
                <option value="3">3课时</option>
              </select>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">课题名称 *</label>
            <input
              type="text"
              value={lesson}
              onChange={(e) => setLesson(e.target.value)}
              placeholder="如：富饶的西沙群岛、观潮…"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">教学要求（可选）</label>
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder="如：重点修辞手法，增加仿写练习，注重朗读指导…"
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none resize-none"
            />
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300
                text-white font-medium px-6 py-2 rounded-lg text-sm transition-colors"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  生成中…
                </span>
              ) : "生成教案"}
            </button>

            <div className="flex gap-2 text-xs text-amber-600">
              {EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => fillExample(ex)} className="hover:text-amber-800 underline">
                  示例{i + 1}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
          )}
        </div>

        {/* Results */}
        {(lessonPlan || teachingGuide) && (
          <div className="bg-white rounded-xl shadow-md border border-amber-100 overflow-hidden">
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setActiveTab("plan")}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  activeTab === "plan"
                    ? "text-amber-700 border-b-2 border-amber-500 bg-amber-50"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                📝 教案
              </button>
              <button
                onClick={() => setActiveTab("guide")}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  activeTab === "guide"
                    ? "text-amber-700 border-b-2 border-amber-500 bg-amber-50"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                🎓 辅导说明
              </button>
            </div>

            <div className="p-6 max-h-[70vh] overflow-y-auto">
              <div className="prose prose-amber prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeTab === "plan" ? lessonPlan : teachingGuide}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Empty */}
        {!lessonPlan && !teachingGuide && !loading && (
          <div className="text-center py-20 text-gray-400 select-none">
            <div className="text-5xl mb-4">📚</div>
            <p className="text-lg font-medium text-gray-500">输入课题，生成教案</p>
            <p className="text-sm mt-1">基于优秀教案参考 + AI 智能生成，鱼渔同授</p>
          </div>
        )}
      </main>
    </div>
  );
}
