"use client";

import Link from "next/link";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "/api";

type UserSummary = {
  username: string;
  role?: string;
  total?: number;
  recent_lessons?: string[];
};

type ReviewItem = {
  id: string;
  username: string;
  lesson: string;
  grade: string;
  status: "pending" | "approved" | "rejected" | string;
  timestamp?: string;
};

type ChunkItem = {
  id: string;
  lesson?: string;
  grade?: string;
  chunk_type?: string;
  doc_type?: string;
  source_role?: string;
  text?: string;
};

type CoverageLesson = {
  lesson: string;
  normative_count: number;
  method_count: number;
  doc_type_counts?: Record<string, number>;
  has_textbook?: boolean;
  has_standard_or_exam?: boolean;
  has_method_case?: boolean;
  missing?: string[];
  status?: string;
};

type CoverageReport = {
  grade?: string;
  semester?: string;
  lesson?: string;
  lessons?: CoverageLesson[];
  total_lessons?: number;
  evidence?: unknown[];
} & Partial<CoverageLesson>;

type EvidenceGapLesson = {
  grade?: string;
  lesson?: string;
  total_records?: number;
  records_with_gaps?: number;
  citation_error_records?: number;
  missing_counts?: Record<string, number>;
  insufficient_block_counts?: Record<string, number>;
  last_seen?: string;
};

type EvidenceGapRecord = {
  id: string;
  username?: string;
  grade?: string;
  lesson?: string;
  timestamp?: string;
  missing_evidence?: string[];
  insufficient_blocks?: string[];
  citation_errors?: string[];
};

type EvidenceGapReport = {
  total_records?: number;
  records_with_gaps?: number;
  citation_error_records?: number;
  gap_rate?: number;
  missing_counts?: Record<string, number>;
  insufficient_block_counts?: Record<string, number>;
  lessons?: EvidenceGapLesson[];
  recent_records?: EvidenceGapRecord[];
};

type FeedbackStats = {
  total_feedbacks?: number;
  avg_rating?: number;
  ratings?: Record<string, number>;
  top_tags?: [string, number][];
};

type HealthCheck = {
  ok?: boolean;
  error?: string;
  free_gb?: number;
  total_gb?: number;
  total_chunks?: number;
};

type HealthReport = {
  status?: string;
  timestamp?: string;
  checks?: Record<string, HealthCheck>;
};

type DeepHealth = {
  status?: string;
  api_key_ok?: boolean;
  model_ok?: boolean;
  chunks?: number;
};

type Dashboard = {
  total_users?: number;
  total_plans?: number;
  review_stats?: { approved?: number; pending?: number };
  grade_coverage?: Record<string, number>;
  teacher_summary?: UserSummary[];
};

type DeviceInfo = {
  mac?: string;
  disk_total_gb?: number;
  disk_free_gb?: number;
  disk_used_pct?: number;
  license?: string;
  version?: string;
};

const DOC_TYPE_OPTIONS = [
  { value: "textbook", label: "教材", role: "normative" },
  { value: "curriculum_standard", label: "课标", role: "normative" },
  { value: "exam_outline", label: "考纲/考试说明", role: "normative" },
  { value: "unit_goal", label: "单元目标", role: "normative" },
  { value: "exam_material", label: "题库/考点资料", role: "normative" },
  { value: "teaching_guidance", label: "教学设计指导", role: "method_case" },
  { value: "teacher_case", label: "老教师教案", role: "method_case" },
  { value: "local_case", label: "本校案例/普通教案", role: "method_case" },
  { value: "training_case", label: "进修校案例", role: "method_case" },
];

const ROLE_LABEL: Record<string, string> = {
  normative: "规范依据",
  method_case: "方法参考",
};

export default function AdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [role, setRole] = useState("");
  const [section, setSection] = useState<Section>("dashboard");

  // Dashboard
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  // Reviews
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  // Prompts
  const [chatPrompt, setChatPrompt] = useState("");
  const [auditPrompt, setAuditPrompt] = useState("");
  // Roles
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedRole, setSelectedRole] = useState("teacher");
  // Chunks
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  // Knowledge upload and coverage
  const [uploadDocType, setUploadDocType] = useState("local_case");
  const [uploadSourceRole, setUploadSourceRole] = useState("method_case");
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [evidenceGaps, setEvidenceGaps] = useState<EvidenceGapReport | null>(null);
  const [coverageGrade, setCoverageGrade] = useState("三年级");
  const [coverageSemester, setCoverageSemester] = useState("上");
  const [coverageLesson, setCoverageLesson] = useState("");
  // Feedback
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  // Health
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [deepHealth, setDeepHealth] = useState<DeepHealth | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("lekai_token") || "";
    setToken(t);
    // 验证角色：非 admin/reviewer 重定向
    if (t) {
      fetch(`${API}/me`, { headers: { Authorization: `Bearer ${t}` } }).then(r => r.json()).then(d => {
        setUsername(d.username || "");
        setRole(d.role || "");
        if (d.role && !["admin", "reviewer"].includes(d.role)) {
          router.push("/");
        }
      }).catch(() => {});
    }
  }, [router]);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }), [token]);

  const loadDashboard = useCallback(async () => {
    const [dr, rr] = await Promise.all([
      fetch(`${API}/admin/dashboard`, { headers }).then(r => r.json()),
      fetch(`${API}/admin/reviews`, { headers }).then(r => r.json()),
    ]);
    setDashboard(dr); setReviews(rr.reviews || []);
    return dr;  // 返回值供调用方直接使用
  }, [headers]);

  const loadHealth = useCallback(async () => {
    const [basic, deep] = await Promise.all([
      fetch(`${API}/admin/health`, { headers }).then(r => r.json()),
      fetch(`${API}/health/deep`, { headers }).then(r => r.json()).catch(() => null),
    ]);
    setHealth(basic);
    setDeepHealth(deep);
  }, [headers]);

  const loadPrompts = useCallback(async () => {
    const p = await fetch(`${API}/admin/prompts`, { headers }).then(r => r.json());
    setChatPrompt(p.chat_prompt || ""); setAuditPrompt(p.audit_prompt || "");
  }, [headers]);

  const loadCoverage = useCallback(async () => {
    const params = new URLSearchParams();
    if (coverageGrade) params.set("grade", coverageGrade);
    if (coverageSemester) params.set("semester", coverageSemester);
    if (coverageLesson.trim()) params.set("lesson", coverageLesson.trim());
    const [data, gaps] = await Promise.all([
      fetch(`${API}/admin/evidence-coverage?${params.toString()}`, { headers }).then(r => r.json()),
      fetch(`${API}/admin/evidence-gaps?${params.toString()}`, { headers }).then(r => r.json()),
    ]);
    setCoverage(data);
    setEvidenceGaps(gaps);
  }, [headers, coverageGrade, coverageSemester, coverageLesson]);

  useEffect(() => {
    if (!token) return;
    if (section === "dashboard" || section === "reviews") loadDashboard();
    if (section === "chunks") fetch(`${API}/admin/chunks`, { headers }).then(r => r.json()).then(d => setChunks(d.chunks || []));
    if (section === "coverage") loadCoverage();
    if (section === "feedback") fetch(`${API}/admin/feedback-stats`, { headers }).then(r => r.json()).then(setFeedbackStats);
    if (section === "health") loadHealth();
    if (section === "prompts") loadPrompts();
    if (section === "roles") loadDashboard().then((dr) => {
      if (dr?.teacher_summary) setUsers(dr.teacher_summary);
    });
  }, [section, token, headers, loadDashboard, loadHealth, loadPrompts, loadCoverage]);

  const savePrompts = async () => {
    try {
      const res = await fetch(`${API}/admin/prompts`, {
        method: "POST", headers, body: JSON.stringify({ chat_prompt: chatPrompt, audit_prompt: auditPrompt }),
      });
      if (!res.ok) { alert("保存失败"); return; }
      alert("提示词已保存，立即生效");
    } catch { console.error("admin API failed"); alert("网络错误，请重试"); }
  };

  const setUserRole = async () => {
    try {
      const res = await fetch(`${API}/admin/users/set-role`, {
        method: "POST", headers, body: JSON.stringify({ username: selectedUser, role: selectedRole }),
      });
      if (!res.ok) { alert("设置失败"); return; }
      alert("角色已更新");
      loadDashboard();
    } catch { console.error("admin API failed"); alert("网络错误，请重试"); }
  };

  const doBackup = async () => {
    try {
      const res = await fetch(`${API}/admin/backup`, { method: "POST", headers });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = `lekai_backup_${new Date().toISOString().slice(0, 10)}.zip`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { console.error("admin API failed"); alert("网络错误，请重试"); }
  };

  const doRestore = async (file: File) => {
    if (!window.confirm("恢复会覆盖用户数据、知识库和向量库。确认继续？")) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/admin/restore`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data.detail || "恢复失败");
        return;
      }
      alert(data.message || "恢复成功，建议重启服务");
      loadDashboard();
    } catch {
      console.error("admin API failed");
      alert("网络错误，请重试");
    }
  };

type Section = "dashboard" | "reviews" | "upload" | "coverage" | "prompts" | "roles" | "feedback" | "chunks" | "device" | "health" | "backup";

  const SECTIONS: { key: Section; label: string; icon: string }[] = [
    { key: "dashboard", label: "仪表盘", icon: "📊" },
    { key: "reviews", label: "审核队列", icon: "✅" },
    { key: "upload", label: "材料入库", icon: "📤" },
    { key: "coverage", label: "依据覆盖", icon: "🧭" },
    { key: "prompts", label: "提示词调优", icon: "🔧" },
    { key: "roles", label: "角色管理", icon: "👥" },
    { key: "chunks", label: "知识库Chunk", icon: "📦" },
    { key: "feedback", label: "反馈统计", icon: "⭐" },
    { key: "device", label: "设备信息", icon: "🔐" },
    { key: "health", label: "系统健康", icon: "🩺" },
    { key: "backup", label: "备份恢复", icon: "💾" },
  ];

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-amber-50">
        <div className="text-center">
          <p className="text-gray-500">请先登录</p>
          <Link href="/" className="text-amber-600 text-sm underline mt-2 block">返回登录</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">⚙️</span>
            <div>
              <h1 className="text-lg font-bold text-gray-800">LeKai 管理端</h1>
              <p className="text-xs text-gray-400">校长仪表盘 · 教研组长审核 · 系统配置</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm text-amber-600 hover:text-amber-800">← 返回主页</Link>
            {(username || role) && (
              <span className="text-xs text-gray-400">{username}{role ? ` · ${role}` : ""}</span>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">
        {/* Sidebar */}
        <nav className="w-48 shrink-0">
          {SECTIONS.map(s => (
            <button key={s.key} onClick={() => setSection(s.key)}
              className={`w-full text-left px-3 py-2 text-sm rounded mb-1 transition-colors ${
                section === s.key ? "bg-amber-600 text-white font-medium" : "text-gray-600 hover:bg-gray-100"
              }`}>
              {s.icon} {s.label}
            </button>
          ))}
        </nav>

        {/* Content */}
        <main className="flex-1">
          {/* Dashboard */}
          {section === "dashboard" && dashboard && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">📊 使用概览</h2>
              <div className="grid grid-cols-4 gap-4 mb-6">
                {[
                  { v: dashboard.total_users, l: "教师数", c: "text-amber-700 bg-amber-50" },
                  { v: dashboard.total_plans, l: "生成教案", c: "text-green-700 bg-green-50" },
                  { v: dashboard.review_stats?.approved, l: "已批准", c: "text-blue-700 bg-blue-50" },
                  { v: dashboard.review_stats?.pending, l: "待审核", c: "text-orange-700 bg-orange-50" },
                ].map((s, i) => (
                  <div key={i} className={`${s.c} rounded-xl p-4 text-center`}>
                    <div className="text-3xl font-bold">{s.v || 0}</div>
                    <div className="text-xs mt-1">{s.l}</div>
                  </div>
                ))}
              </div>

              <h3 className="text-sm font-semibold text-gray-600 mb-2">年级覆盖</h3>
              <div className="flex gap-2 flex-wrap mb-6">
                {(Object.entries(dashboard.grade_coverage || {}) as [string, number][]).map(([g, n]) => (
                  <span key={g} className="bg-amber-100 text-amber-800 text-sm px-3 py-1 rounded-full">{g}: {n}课</span>
                ))}
                {Object.keys(dashboard.grade_coverage || {}).length === 0 && (
                  <span className="text-sm text-gray-400">暂无数据</span>
                )}
              </div>

              <h3 className="text-sm font-semibold text-gray-600 mb-2">教师活跃度</h3>
              <div className="bg-white rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr><th className="text-left px-4 py-2">教师</th><th className="text-right px-4 py-2">生成数</th><th className="text-left px-4 py-2">最近课题</th></tr>
                  </thead>
                  <tbody>
                    {(dashboard.teacher_summary || []).map((t) => (
                      <tr key={t.username} className="border-t">
                        <td className="px-4 py-2 font-medium">{t.username}</td>
                        <td className="px-4 py-2 text-right">{t.total || 0}</td>
                        <td className="px-4 py-2 text-gray-500 text-xs">{(t.recent_lessons || []).slice(0, 3).join(" · ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Upload Lesson */}
          {section === "upload" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">📤 材料入库</h2>
              <p className="text-sm text-gray-500 mb-4">上传 .md / .txt / .docx / .pdf 文档，必须先标注材料类型和角色。扫描 PDF 会自动 OCR 并保留页码与高亮定位。</p>
              <div className="bg-white rounded-lg border p-6">
                <div className="grid md:grid-cols-2 gap-4 mb-4">
                  <label className="block">
                    <span className="text-xs font-medium text-gray-600 block mb-1">文档类型</span>
                    <select value={uploadDocType} onChange={e => {
                      const next = e.target.value;
                      setUploadDocType(next);
                      setUploadSourceRole(DOC_TYPE_OPTIONS.find(opt => opt.value === next)?.role || "method_case");
                    }} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
                      <optgroup label="规范依据">
                        {DOC_TYPE_OPTIONS.filter(opt => opt.role === "normative").map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="方法参考">
                        {DOC_TYPE_OPTIONS.filter(opt => opt.role === "method_case").map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </optgroup>
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium text-gray-600 block mb-1">材料角色</span>
                    <select value={uploadSourceRole} onChange={e => setUploadSourceRole(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
                      <option value="normative">规范依据</option>
                      <option value="method_case">方法参考</option>
                    </select>
                  </label>
                </div>
                <div className="mb-4 rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  当前标注：{DOC_TYPE_OPTIONS.find(opt => opt.value === uploadDocType)?.label || uploadDocType} / {ROLE_LABEL[uploadSourceRole] || uploadSourceRole}
                </div>
                <input type="file" accept=".md,.txt,.docx,.pdf,application/pdf" onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  const expectedRole = DOC_TYPE_OPTIONS.find(opt => opt.value === uploadDocType)?.role;
                  if (!expectedRole || expectedRole !== uploadSourceRole) {
                    alert("文档类型和材料角色不匹配，请重新选择");
                    e.target.value = "";
                    return;
                  }
                  const form = new FormData();
                  form.append("file", f);
                  form.append("doc_type", uploadDocType);
                  form.append("source_role", uploadSourceRole);
                  try {
                    const res = await fetch(`${API}/admin/upload-lesson`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
                    const d = await res.json();
                    alert(d.ok ? d.message : (d.detail || d.message || "上传失败"));
                    if (d.ok) loadCoverage();
                  } catch { alert("上传失败"); }
                  e.target.value = "";
                }} className="text-sm" />
              </div>
            </div>
          )}

          {/* Evidence Coverage */}
          {section === "coverage" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">🧭 依据覆盖度</h2>
              <div className="bg-white rounded-lg border p-4 mb-4">
                <div className="flex flex-wrap gap-2 items-end">
                  <label className="block">
                    <span className="text-xs text-gray-500 block mb-1">年级</span>
                    <select value={coverageGrade} onChange={e => setCoverageGrade(e.target.value)}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
                      {["一年级","二年级","三年级","四年级","五年级","六年级"].map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-xs text-gray-500 block mb-1">册次</span>
                    <select value={coverageSemester} onChange={e => setCoverageSemester(e.target.value)}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
                      <option value="上">上册</option>
                      <option value="下">下册</option>
                    </select>
                  </label>
                  <label className="block flex-1 min-w-48">
                    <span className="text-xs text-gray-500 block mb-1">课题（留空查看汇总）</span>
                    <input value={coverageLesson} onChange={e => setCoverageLesson(e.target.value)}
                      placeholder="如：秋天的雨"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
                  </label>
                  <button onClick={loadCoverage}
                    className="bg-amber-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-amber-700">
                    检查
                  </button>
                </div>
              </div>
              {evidenceGaps && <EvidenceGapPanel report={evidenceGaps} />}
              {coverage && coverage.lesson && (
                <CoverageCard item={coverage as CoverageLesson} title={`《${coverage.lesson}》`} />
              )}
              {coverage && !coverage.lesson && (
                <div>
                  <div className="text-sm text-gray-500 mb-3">共 {coverage.total_lessons || 0} 个课题</div>
                  {(coverage.lessons || []).map(item => (
                    <CoverageCard key={item.lesson} item={item} title={`《${item.lesson}》`} />
                  ))}
                  {(coverage.lessons || []).length === 0 && <div className="text-sm text-gray-400">暂无知识库材料</div>}
                </div>
              )}
            </div>
          )}

          {/* Reviews */}
          {section === "reviews" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">✅ 审核队列</h2>
              {reviews.length === 0 && <p className="text-gray-400 text-sm">暂无待审核教案</p>}
              {reviews.map((r) => (
                <div key={r.id} className={`bg-white rounded-lg border p-4 mb-2 ${r.status === "pending" ? "border-l-4 border-l-yellow-400" : r.status === "approved" ? "border-l-4 border-l-green-400" : "border-l-4 border-l-red-400"}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{r.username}</span>
                      <span className="text-gray-400 mx-2">·</span>
                      <span>《{r.lesson}》</span>
                      <span className="text-gray-400 mx-2">·</span>
                      <span className="text-sm text-gray-500">{r.grade} · {r.timestamp?.slice(0, 16)}</span>
                      <span className={`ml-3 text-xs px-2 py-0.5 rounded-full ${
                        r.status === "pending" ? "bg-yellow-100 text-yellow-700" :
                        r.status === "approved" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                      }`}>
                        {r.status === "pending" ? "待审" : r.status === "approved" ? "已通过" : "已打回"}
                      </span>
                    </div>
                    {r.status === "pending" && (
                      <div className="flex gap-2">
                        <button onClick={async () => {
                          try { await fetch(`${API}/admin/reviews/${r.id}/approve`, { method: "POST", headers }); loadDashboard(); } catch { console.error("approve failed"); }
                        }} className="bg-green-500 text-white text-sm px-4 py-1 rounded hover:bg-green-600">通过</button>
                        <button onClick={async () => {
                          try { await fetch(`${API}/admin/reviews/${r.id}/reject`, { method: "POST", headers, body: JSON.stringify({ comment: "" }) }); loadDashboard(); } catch { console.error("reject failed"); }
                        }} className="bg-red-500 text-white text-sm px-4 py-1 rounded hover:bg-red-600">打回</button>
                        <button onClick={async () => {
                          const section = prompt("标注章节（教材分析/教学目标/教学过程/板书设计/作业布置）：");
                          const annType = prompt("类型（praise=表扬/improve=改进/note=备注）：");
                          const text = prompt("标注内容：");
                          if (section && annType && text) {
                            await fetch(`${API}/admin/annotations`, {
                              method: "POST", headers, body: JSON.stringify({ review_id: r.id, section, type: annType, text }),
                            });
                          }
                        }} className="bg-purple-500 text-white text-sm px-3 py-1 rounded hover:bg-purple-600">✏️ 标注</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Prompts */}
          {section === "prompts" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">🔧 提示词调优</h2>
              <p className="text-sm text-gray-500 mb-4">修改后立即生效，无需重启。留空则使用系统默认提示词。</p>
              <div className="bg-white rounded-lg border p-4 mb-4">
                <label className="text-sm font-semibold text-gray-700 mb-2 block">问答提示词 (chat_prompt)</label>
                <textarea value={chatPrompt} onChange={e => setChatPrompt(e.target.value)}
                  rows={8} className="w-full border border-gray-300 rounded-lg p-3 text-sm font-mono"
                  placeholder="留空使用默认提示词" />
              </div>
              <div className="bg-white rounded-lg border p-4 mb-4">
                <label className="text-sm font-semibold text-gray-700 mb-2 block">审计提示词 (audit_prompt)</label>
                <textarea value={auditPrompt} onChange={e => setAuditPrompt(e.target.value)}
                  rows={8} className="w-full border border-gray-300 rounded-lg p-3 text-sm font-mono"
                  placeholder="留空使用默认提示词" />
              </div>
              <button onClick={savePrompts} className="bg-amber-600 text-white px-6 py-2 rounded-lg hover:bg-amber-700 text-sm">
                保存提示词
              </button>
            </div>
          )}

          {/* Roles */}
          {section === "roles" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">👥 角色管理</h2>

              {/* Create User */}
              <div className="bg-white rounded-lg border p-4 mb-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">➕ 创建用户</h3>
                <div className="flex gap-2">
                  <input type="text" id="new-user-name" placeholder="用户名" className="border rounded px-2 py-1 text-sm w-32" />
                  <input type="password" id="new-user-pass" placeholder="密码" className="border rounded px-2 py-1 text-sm w-32" />
                  <button onClick={async () => {
                    const u = (document.getElementById("new-user-name") as HTMLInputElement)?.value;
                    const p = (document.getElementById("new-user-pass") as HTMLInputElement)?.value;
                    if (!u || !p) { alert("请填写用户名和密码"); return; }
                    try {
                      const res = await fetch(`${API}/register`, { method: "POST", headers, body: JSON.stringify({ username: u, password: p }) });
                      if (res.ok) { alert("用户创建成功"); loadDashboard(); }
                      else { const d = await res.json(); alert(d.detail); }
                    } catch { alert("网络错误"); }
                  }} className="bg-amber-600 text-white text-sm px-3 py-1 rounded">创建</button>
                </div>
              </div>

              {/* Batch Import Users */}
              <div className="bg-white rounded-lg border p-4 mb-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">📋 批量导入教师</h3>
                <p className="text-xs text-gray-400 mb-2">CSV 格式：每行一个用户，逗号分隔用户名和密码</p>
                <textarea id="csv-input" rows={4} placeholder={"zhang_teacher,zhang123\nli_teacher,li123\nwang_teacher,wang123"}
                  className="w-full border rounded px-3 py-2 text-xs font-mono mb-2" />
                <div className="flex gap-2 items-center">
                  <button onClick={async () => {
                    const csv = (document.getElementById("csv-input") as HTMLTextAreaElement)?.value;
                    if (!csv.trim()) { alert("请输入 CSV 内容"); return; }
                    try {
                      const res = await fetch(`${API}/admin/users/import`, { method: "POST", headers, body: JSON.stringify({ csv }) });
                      const d = await res.json();
                      if (d.ok) {
                        let msg = `导入完成：成功 ${d.imported} 人`;
                        if (d.failed > 0) {
                          msg += `，失败 ${d.failed} 人：` + d.results.failed.map((f: { username?: string; line?: number }) => f.username || f.line).join(", ");
                        }
                        alert(msg);
                        loadDashboard();
                      } else {
                        alert(d.detail || "导入失败");
                      }
                    } catch { alert("网络错误"); }
                  }} className="bg-green-600 text-white text-sm px-3 py-1 rounded hover:bg-green-700">批量导入</button>
                  <span className="text-xs text-gray-400">示例：用户名,密码</span>
                </div>
              </div>
              <div className="bg-white rounded-lg border p-4 mb-4">
                <div className="flex gap-3 items-end">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">用户</label>
                    <select value={selectedUser} onChange={e => setSelectedUser(e.target.value)}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
                      <option value="">选择用户</option>
                      {(users || []).map((u) => (
                        <option key={u.username} value={u.username}>{u.username} ({u.total || 0}篇)</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">角色</label>
                    <select value={selectedRole} onChange={e => setSelectedRole(e.target.value)}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
                      <option value="teacher">教师 (teacher)</option>
                      <option value="reviewer">教研组长 (reviewer)</option>
                      <option value="admin">管理员 (admin)</option>
                    </select>
                  </div>
                  <button onClick={setUserRole} className="bg-amber-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-amber-700">
                    设置角色
                  </button>
                </div>
              </div>
              <div className="bg-white rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr><th className="text-left px-4 py-2">用户名</th><th className="text-left px-4 py-2">当前角色</th></tr>
                  </thead>
                  <tbody>
                    {(users || []).map((u) => (
                      <tr key={u.username} className="border-t">
                        <td className="px-4 py-2 font-medium">{u.username}</td>
                        <td className="px-4 py-2">{u.role || "teacher"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Device Info */}
          {section === "device" && (
            <DeviceInfoPanel token={token} />
          )}

          {/* Health */}
          {section === "health" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">🩺 系统健康</h2>
              {health && (
                <div className="space-y-3">
                  {deepHealth && (
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { label: "DeepSeek API", ok: deepHealth.api_key_ok, detail: deepHealth.api_key_ok ? "可调用" : "不可用" },
                        { label: "Embedding 模型", ok: deepHealth.model_ok, detail: deepHealth.model_ok ? "已加载" : "加载失败" },
                        { label: "知识库索引", ok: (deepHealth.chunks || 0) > 0, detail: `${deepHealth.chunks || 0} chunks` },
                      ].map(item => (
                        <div key={item.label} className={`bg-white rounded-lg border p-4 ${item.ok ? "border-l-4 border-l-green-400" : "border-l-4 border-l-red-400"}`}>
                          <div className="text-sm font-medium">{item.label}</div>
                          <div className={`text-sm mt-1 ${item.ok ? "text-green-600" : "text-red-600"}`}>{item.detail}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {Object.entries(health.checks || {}).map(([k, v]) => (
                    <div key={k} className={`bg-white rounded-lg border p-4 flex items-center justify-between ${
                      v.ok ? "border-l-4 border-l-green-400" : "border-l-4 border-l-red-400"
                    }`}>
                      <div>
                        <span className="font-medium text-sm">{k}</span>
                        <span className="text-xs text-gray-400 ml-2">
                          {k === "disk" && `${v.free_gb}GB 可用 / ${v.total_gb}GB`}
                          {k === "chromadb" && `${v.total_chunks} chunks`}
                        </span>
                      </div>
                      <span className={`text-sm font-medium ${v.ok ? "text-green-600" : "text-red-600"}`}>
                        {v.ok ? "正常" : v.error || "异常"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Chunks */}
          {section === "chunks" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">📦 知识库 Chunk ({chunks.length})</h2>
              {chunks.map((c) => (
                <div key={c.id} className="bg-white rounded-lg border p-3 mb-1 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{c.lesson || "—"}</span>
                    <span className="text-gray-400">{c.grade} · {c.chunk_type} · {ROLE_LABEL[c.source_role || ""] || c.source_role || "未标注"}</span>
                  </div>
                  {c.doc_type && (
                    <div className="mb-1 text-[11px] text-gray-400">
                      {DOC_TYPE_OPTIONS.find(opt => opt.value === c.doc_type)?.label || c.doc_type}
                    </div>
                  )}
                  <p className="text-gray-500 truncate">{c.text}</p>
                </div>
              ))}
            </div>
          )}

          {/* Feedback */}
          {section === "feedback" && feedbackStats && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">⭐ 教案反馈统计</h2>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-white rounded-lg border p-4 text-center">
                  <div className="text-2xl font-bold text-purple-700">{feedbackStats.total_feedbacks || 0}</div>
                  <div className="text-xs text-gray-500">总反馈数</div>
                </div>
                <div className="bg-white rounded-lg border p-4 text-center">
                  <div className="text-2xl font-bold text-purple-700">{feedbackStats.avg_rating || 0}</div>
                  <div className="text-xs text-gray-500">平均评分</div>
                </div>
              </div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">评分分布</h3>
              <div className="bg-white rounded-lg border p-4 mb-4">
                {[5,4,3,2,1].map(s => {
                  const count = feedbackStats.ratings?.[String(s)] || 0;
                  const max = Math.max(1, ...(Object.values(feedbackStats.ratings || {1: 1}) as number[]));
                  return (
                    <div key={s} className="flex items-center gap-2 mb-1">
                      <span className="text-xs w-8">{s}星</span>
                      <div className="flex-1 bg-gray-100 rounded h-4">
                        <div className="bg-purple-400 rounded h-4" style={{ width: `${(count/max)*100}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-8">{count}</span>
                    </div>
                  );
                })}
              </div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">高频标签</h3>
              <div className="flex gap-2 flex-wrap">
                {(feedbackStats.top_tags || []).map(([tag, count]: [string, number]) => (
                  <span key={tag} className="bg-purple-50 text-purple-700 text-xs px-2 py-1 rounded-full">{tag} ({count})</span>
                ))}
              </div>
            </div>
          )}

          {/* Backup */}
          {section === "backup" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">💾 备份恢复</h2>
              <div className="bg-white rounded-lg border p-6 text-center">
                <p className="text-sm text-gray-500 mb-4">备份包含用户数据、教案知识库、配置文件（API Key 已脱敏）</p>
                <button onClick={doBackup}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-blue-700">
                  下载备份 (.zip)
                </button>
                <div className="mt-6 border-t pt-5">
                  <p className="text-sm text-gray-500 mb-3">从备份 zip 恢复数据。恢复后请重启服务刷新内存索引。</p>
                  <input
                    type="file"
                    accept=".zip,application/zip"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) doRestore(file);
                      e.target.value = "";
                    }}
                    className="text-sm"
                  />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function CountTags({ counts, emptyText }: { counts?: Record<string, number>; emptyText: string }) {
  const items = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
  if (items.length === 0) return <span className="text-xs text-gray-400">{emptyText}</span>;
  return (
    <div className="flex gap-1 flex-wrap">
      {items.map(([label, count]) => (
        <span key={label} className="text-[11px] bg-red-50 text-red-700 px-2 py-0.5 rounded-full">
          {label}: {count}
        </span>
      ))}
    </div>
  );
}

function EvidenceGapPanel({ report }: { report: EvidenceGapReport }) {
  const gapRate = Math.round((report.gap_rate || 0) * 100);
  const lessons = (report.lessons || []).filter(item => (item.records_with_gaps || 0) > 0).slice(0, 6);
  const recent = (report.recent_records || []).slice(0, 5);
  return (
    <div className="bg-white rounded-lg border p-4 mb-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">生成记录中的依据不足</h3>
          <p className="text-xs text-gray-500 mt-1">统计真实历史记录，帮助判断哪些课需要优先补教材、课标、考纲或单元材料。</p>
        </div>
        <span className={`text-xs px-2 py-1 rounded ${gapRate ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {gapRate}% 记录有缺口
        </span>
      </div>
      <div className="grid md:grid-cols-3 gap-3 mb-4">
        <div className="rounded border bg-gray-50 p-3">
          <div className="text-2xl font-bold text-gray-800">{report.total_records || 0}</div>
          <div className="text-xs text-gray-500">生成记录</div>
        </div>
        <div className="rounded border bg-red-50 p-3">
          <div className="text-2xl font-bold text-red-700">{report.records_with_gaps || 0}</div>
          <div className="text-xs text-red-700">依据不足记录</div>
        </div>
        <div className="rounded border bg-amber-50 p-3">
          <div className="text-2xl font-bold text-amber-700">{report.citation_error_records || 0}</div>
          <div className="text-xs text-amber-700">引用校验异常</div>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-3 mb-4">
        <div>
          <div className="text-xs font-medium text-gray-600 mb-2">缺失材料类型</div>
          <CountTags counts={report.missing_counts} emptyText="暂无缺失记录" />
        </div>
        <div>
          <div className="text-xs font-medium text-gray-600 mb-2">依据不足模块</div>
          <CountTags counts={report.insufficient_block_counts} emptyText="暂无不足模块" />
        </div>
      </div>
      {lessons.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-gray-600 mb-2">优先补资料课题</div>
          <div className="space-y-2">
            {lessons.map(item => (
              <div key={`${item.grade}-${item.lesson}`} className="rounded border px-3 py-2 text-xs">
                <div className="flex justify-between gap-3 mb-1">
                  <span className="font-medium text-gray-700">{item.grade}《{item.lesson}》</span>
                  <span className="text-red-600">{item.records_with_gaps || 0}/{item.total_records || 0} 条有缺口</span>
                </div>
                <CountTags counts={item.missing_counts} emptyText="暂无缺失记录" />
              </div>
            ))}
          </div>
        </div>
      )}
      {recent.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-2">最近依据不足记录</div>
          <div className="space-y-1">
            {recent.map(item => (
              <div key={`${item.username}-${item.id}`} className="text-xs text-gray-500">
                {item.timestamp} · {item.username} · {item.grade}《{item.lesson}》 · {(item.missing_evidence || []).join("；") || (item.insufficient_blocks || []).join("、")}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CoverageCard({ item, title }: { item: CoverageLesson; title: string }) {
  const missing = item.missing || [];
  const counts = item.doc_type_counts || {};
  return (
    <div className={`bg-white rounded-lg border p-4 mb-3 ${missing.length === 0 ? "border-l-4 border-l-green-400" : "border-l-4 border-l-amber-400"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
          <div className="text-xs text-gray-500 mt-1">
            规范依据 {item.normative_count || 0} 条 · 方法参考 {item.method_count || 0} 条
          </div>
        </div>
        <span className={`text-xs px-2 py-1 rounded ${missing.length === 0 ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>
          {missing.length === 0 ? "资料可用" : "依据不足"}
        </span>
      </div>
      <div className="grid md:grid-cols-3 gap-2 mt-3 text-xs">
        <div className={item.has_textbook ? "text-green-700" : "text-red-600"}>教材：{item.has_textbook ? "已覆盖" : "缺少"}</div>
        <div className={item.has_standard_or_exam ? "text-green-700" : "text-red-600"}>课标/考纲/单元目标：{item.has_standard_or_exam ? "已覆盖" : "缺少"}</div>
        <div className={item.has_method_case ? "text-green-700" : "text-red-600"}>方法案例：{item.has_method_case ? "已覆盖" : "缺少"}</div>
      </div>
      {missing.length > 0 && (
        <div className="mt-3 rounded bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-800">
          {missing.join("；")}
        </div>
      )}
      {Object.keys(counts).length > 0 && (
        <div className="flex gap-1 flex-wrap mt-3">
          {Object.entries(counts).map(([docType, count]) => (
            <span key={docType} className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
              {DOC_TYPE_OPTIONS.find(opt => opt.value === docType)?.label || docType}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function DeviceInfoPanel({ token }: { token: string }) {
  const [info, setInfo] = useState<DeviceInfo | null>(null);
  useEffect(() => {
    fetch(`${API}/admin/device-info`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(setInfo).catch(() => {});
  }, [token]);
  if (!info) return <div><h2 className="text-lg font-bold text-gray-800 mb-4">🔐 设备信息</h2><p className="text-gray-400 text-sm">加载中...</p></div>;
  return (
    <div>
      <h2 className="text-lg font-bold text-gray-800 mb-4">🔐 设备信息</h2>
      <div className="bg-white rounded-lg border p-4 space-y-2 text-sm">
        <div className="flex justify-between"><span className="text-gray-500">MAC地址</span><code>{info.mac}</code></div>
        <div className="flex justify-between"><span className="text-gray-500">磁盘容量</span><span>{info.disk_total_gb}GB（可用 {info.disk_free_gb}GB / 已用 {info.disk_used_pct}%）</span></div>
        <div className="flex justify-between"><span className="text-gray-500">授权状态</span><span className={info.license === "已授权" ? "text-green-600 font-medium" : "text-red-600 font-medium"}>{info.license}</span></div>
        <div className="flex justify-between"><span className="text-gray-500">系统版本</span><span>{info.version}</span></div>
      </div>
    </div>
  );
}
