"use client";

import { useState, useEffect, useCallback } from "react";

const API = "/api";

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [role, setRole] = useState("");
  const [section, setSection] = useState<Section>("dashboard");

  // Dashboard
  const [dashboard, setDashboard] = useState<any>(null);
  // Reviews
  const [reviews, setReviews] = useState<any[]>([]);
  // Prompts
  const [chatPrompt, setChatPrompt] = useState("");
  const [auditPrompt, setAuditPrompt] = useState("");
  // Roles
  const [users, setUsers] = useState<any[]>([]);
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedRole, setSelectedRole] = useState("teacher");
  // Chunks
  const [chunks, setChunks] = useState<any[]>([]);
  // Feedback
  const [feedbackStats, setFeedbackStats] = useState<any>(null);
  // Health
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const t = localStorage.getItem("lekai_token") || "";
    setToken(t);
    // 验证角色：非 admin/reviewer 重定向
    if (t) {
      fetch("/api/me", { headers: { Authorization: `Bearer ${t}` } }).then(r => r.json()).then(d => {
        if (d.role && !["admin", "reviewer"].includes(d.role)) {
          window.location.href = "/";
        }
      }).catch(() => {});
    }
  }, []);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const loadDashboard = async () => {
    const [dr, rr] = await Promise.all([
      fetch(`${API}/admin/dashboard`, { headers }).then(r => r.json()),
      fetch(`${API}/admin/reviews`, { headers }).then(r => r.json()),
    ]);
    setDashboard(dr); setReviews(rr.reviews || []);
    return dr;  // 返回值供调用方直接使用
  };

  const loadHealth = async () => {
    const h = await fetch(`${API}/admin/health`, { headers }).then(r => r.json());
    setHealth(h);
  };

  const loadPrompts = async () => {
    const p = await fetch(`${API}/admin/prompts`, { headers }).then(r => r.json());
    setChatPrompt(p.chat_prompt || ""); setAuditPrompt(p.audit_prompt || "");
  };

  const loadUsers = async () => {
    // Get users from dashboard data
    if (dashboard?.teacher_summary) {
      setUsers(dashboard.teacher_summary);
    }
  };

  useEffect(() => {
    if (!token) return;
    if (section === "dashboard" || section === "reviews") loadDashboard();
    if (section === "chunks") fetch(`${API}/admin/chunks`, { headers }).then(r => r.json()).then(d => setChunks(d.chunks || []));
    if (section === "feedback") fetch(`${API}/admin/feedback-stats`, { headers }).then(r => r.json()).then(setFeedbackStats);
    if (section === "health") loadHealth();
    if (section === "prompts") loadPrompts();
    if (section === "roles") loadDashboard().then((dr) => {
      if (dr?.teacher_summary) setUsers(dr.teacher_summary);
    });
  }, [section, token]);

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

type Section = "dashboard" | "reviews" | "prompts" | "roles" | "feedback" | "chunks" | "health" | "backup";
    { key: "dashboard", label: "仪表盘", icon: "📊" },
    { key: "reviews", label: "审核队列", icon: "✅" },
    { key: "prompts", label: "提示词调优", icon: "🔧" },
    { key: "roles", label: "角色管理", icon: "👥" },
    { key: "chunks", label: "知识库Chunk", icon: "📦" },
    { key: "feedback", label: "反馈统计", icon: "⭐" },
    { key: "health", label: "系统健康", icon: "🩺" },
    { key: "backup", label: "备份恢复", icon: "💾" },
  ];

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-amber-50">
        <div className="text-center">
          <p className="text-gray-500">请先登录</p>
          <a href="/" className="text-amber-600 text-sm underline mt-2 block">返回登录</a>
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
            <a href="/" className="text-sm text-amber-600 hover:text-amber-800">← 返回主页</a>
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
                    {(dashboard.teacher_summary || []).map((t: any) => (
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

          {/* Reviews */}
          {section === "reviews" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">✅ 审核队列</h2>
              {reviews.length === 0 && <p className="text-gray-400 text-sm">暂无待审核教案</p>}
              {reviews.map((r: any) => (
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
                          try { await fetch(`${API}/admin/reviews/${r.id}/reject`, { method: "POST", headers }); loadDashboard(); } catch { console.error("reject failed"); }
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
              <div className="bg-white rounded-lg border p-4 mb-4">
                <div className="flex gap-3 items-end">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">用户</label>
                    <select value={selectedUser} onChange={e => setSelectedUser(e.target.value)}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
                      <option value="">选择用户</option>
                      {(users || []).map((u: any) => (
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
                    {(users || []).map((u: any) => (
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

          {/* Health */}
          {section === "health" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-4">🩺 系统健康</h2>
              {health && (
                <div className="space-y-3">
                  {Object.entries(health.checks || {}).map(([k, v]: [string, any]) => (
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
              {chunks.map((c: any) => (
                <div key={c.id} className="bg-white rounded-lg border p-3 mb-1 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{c.lesson || "—"}</span>
                    <span className="text-gray-400">{c.grade} · {c.chunk_type}</span>
                  </div>
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
                  const max = Math.max(1, ...Object.values(feedbackStats.ratings || {1:1}));
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
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
