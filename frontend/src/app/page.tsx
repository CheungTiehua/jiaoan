"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import type { CSSProperties } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import MermaidMindmap from "../components/MermaidMindmap";

const API = process.env.NEXT_PUBLIC_API_URL || "/api";

type Tab = "exam" | "peer" | "plan" | "guide" | "lessonMindmap" | "methodMindmap";
type AuxSection = "exam" | "peer" | "guide";

interface TextbookGrade { grade: string; semesters: { name: string; units: { name: string; lessons: { title: string; type?: string }[] }[] }[] }
interface HistoryItem { id: string; timestamp: string; grade: string; lesson: string; exam_analysis: string; peer_analysis: string }
interface CollabGroup { name: string; members?: string[] }
interface CollabComment { username?: string; text?: string }
interface GroupPlan { shared_by?: string; lesson?: string; grade?: string; timestamp?: string; comments?: CollabComment[] }
interface GroupTask { lesson?: string; assigned_to?: string; done?: boolean; status?: string }
interface WifiNetwork { ssid: string; signal: number; security?: string }
type SseEvent = { event: string; data: Record<string, unknown> };

interface TeachingEvidence {
  id: string;
  source_role: "normative" | "method_case";
  doc_type: string;
  doc_title: string;
  page_num?: number;
  page_width?: number;
  page_height?: number;
  bbox?: number[];
  content: string;
  source_file_id?: string;
  source_file_name?: string;
  source_hash?: string;
  page_image_url?: string;
  dee_url?: string;
}

interface GeneratedBlock {
  id: string;
  block_type: string;
  evidence_ids: string[];
  reference_ids: string[];
  evidence_status: "supported" | "insufficient" | "not_required";
}

function getErrorMessage(error: unknown, fallback = "操作失败") {
  return error instanceof Error ? error.message : fallback;
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    const parsed = JSON.parse(dataLines.join("\n"));
    return { event, data: parsed };
  } catch {
    return null;
  }
}

const DOC_TYPE_LABEL: Record<string, string> = {
  textbook: "教材",
  curriculum_standard: "课标",
  exam_outline: "考纲",
  unit_goal: "单元目标",
  exam_material: "考试资料",
  teaching_guidance: "教学设计指导",
  teacher_case: "老教师案例",
  local_case: "本校案例",
  training_case: "进修校案例",
};

const BLOCK_TYPE_LABEL: Record<string, string> = {
  textbook_analysis: "教材分析",
  student_analysis: "学情分析",
  teaching_goal: "教学目标",
  key_point: "教学重难点",
  exam_point: "考点分析",
  teaching_activity: "教学活动",
  homework: "作业",
  board_design: "板书",
  guidance: "辅导/反思",
};

function bboxOverlayStyle(item: TeachingEvidence): CSSProperties | null {
  const box = item.bbox || [];
  if (box.length < 4 || !item.page_width || !item.page_height) return null;
  const [x0, y0, x1, y1] = box;
  const width = Math.max(0, x1 - x0);
  const height = Math.max(0, y1 - y0);
  if (width <= 0 || height <= 0) return null;
  return {
    left: `${(x0 / item.page_width) * 100}%`,
    top: `${(y0 / item.page_height) * 100}%`,
    width: `${(width / item.page_width) * 100}%`,
    height: `${(height / item.page_height) * 100}%`,
  };
}

export default function Home() {
  // Auth
  const [token, setToken] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [userRole, setUserRole] = useState<string>("");
  const [authUser, setAuthUser] = useState("");
  const [authPass, setAuthPass] = useState("");
  const [authError, setAuthError] = useState("");

  const [lastPlanId, setLastPlanId] = useState<string>("");
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [evaluation, setEvaluation] = useState("");
  const [evaluating, setEvaluating] = useState(false);

  // Unit plan
  const [unitName, setUnitName] = useState("");
  const [unitPlan, setUnitPlan] = useState("");
  const [loadingUnit, setLoadingUnit] = useState(false);

  // Collab
  const [showCollab, setShowCollab] = useState(false);
  const [groups, setGroups] = useState<CollabGroup[]>([]);
  const [myGroups, setMyGroups] = useState<string[]>([]);
  const [activeGroup, setActiveGroup] = useState("");
  const [groupPlans, setGroupPlans] = useState<GroupPlan[]>([]);
  const [groupTasks, setGroupTasks] = useState<GroupTask[]>([]);
  const [newGroupName, setNewGroupName] = useState("");
  const [collabComment, setCollabComment] = useState("");

  // Reflection
  const [reflection, setReflection] = useState("");
  const [loadingReflect, setLoadingReflect] = useState(false);

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
  const [sectionLoading, setSectionLoading] = useState<AuxSection | "">("");
  const [generationPhase, setGenerationPhase] = useState("");
  const [generationStartedAt, setGenerationStartedAt] = useState<number | null>(null);
  const [generationElapsed, setGenerationElapsed] = useState(0);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("plan");
  const [examAnalysis, setExamAnalysis] = useState("");
  const [peerAnalysis, setPeerAnalysis] = useState("");
  const [lessonPlan, setLessonPlan] = useState("");
  const [teachingGuide, setTeachingGuide] = useState("");
  const [teachingEvidence, setTeachingEvidence] = useState<TeachingEvidence[]>([]);
  const [generatedBlocks, setGeneratedBlocks] = useState<GeneratedBlock[]>([]);
  const [missingEvidence, setMissingEvidence] = useState<string[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<TeachingEvidence | null>(null);

  // Mindmap
  const [lessonMindmap, setLessonMindmap] = useState("");
  const [methodMindmap, setMethodMindmap] = useState("");
  const [mindmapLoading, setMindmapLoading] = useState(false);
  const [mindmapError, setMindmapError] = useState("");
  const [mindmapSaveStatus, setMindmapSaveStatus] = useState("");

  // Revision
  const [revising, setRevising] = useState(false);
  const [revisionInput, setRevisionInput] = useState("");
  const [revisionHistory, setRevisionHistory] = useState<string[]>([]);

  // Setup wizard
  const [needsSetup, setNeedsSetup] = useState(false);
  const [setupStep, setSetupStep] = useState(1);
  const [wifiList, setWifiList] = useState<WifiNetwork[]>([]);
  const [wifiSSID, setWifiSSID] = useState("");
  const [wifiPass, setWifiPass] = useState("");
  const [wifiScanning, setWifiScanning] = useState(false);
  const [setupAdminPass, setSetupAdminPass] = useState("");
  const [setupApiKey, setSetupApiKey] = useState("");
  const [setupError, setSetupError] = useState("");

  // Init: load token from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("lekai_token");
    if (saved) setToken(saved);
    // 检查是否需要初始化
    fetch("/api/setup/status").then(r => r.json()).then(d => {
      if (d.needs_setup) setNeedsSetup(true);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => {
        if (!d.username) {
          setToken("");
          setUsername("");
          setUserRole("");
          localStorage.removeItem("lekai_token");
          return;
        }
        setUsername(d.username);
        setUserRole(d.role || "teacher");
      })
      .catch(() => {});
  }, [token]);

  // Load textbooks
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${API}/textbooks`, { signal: ctrl.signal }).then(r => r.json()).then(d => setTextbooks(d.textbooks || [])).catch(() => {});
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!generationStartedAt) {
      setGenerationElapsed(0);
      return;
    }
    const timer = window.setInterval(() => {
      setGenerationElapsed(Math.floor((Date.now() - generationStartedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [generationStartedAt]);

  // Auth handlers
  const doAuth = async () => {
    setAuthError("");
    try {
      const res = await fetch(`${API}/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: authUser, password: authPass }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "操作失败");
      setToken(d.token);
      setUsername(d.username || authUser);
      setUserRole(d.role || "teacher");
      localStorage.setItem("lekai_token", d.token);
    } catch (e: unknown) { setAuthError(getErrorMessage(e)); }
  };

  const doLogout = () => {
    fetch(`${API}/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
    setToken(""); setUsername(""); localStorage.removeItem("lekai_token");
    setHistory([]); setShowHistory(false);
  };

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API}/history`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setHistory(d.history || []); setShowHistory(true); }
    } catch { }
  };

  const loadCollab = async () => {
    try {
      const res = await fetch(`${API}/collab/groups`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setGroups(d.groups || []); setMyGroups(d.my_groups || []);
        if (d.my_groups?.length > 0) setActiveGroup(d.my_groups[0]);
      }
    } catch { }
  };

  useEffect(() => {
    if (!showCollab || !token || !activeGroup) return;
    const ctrl = new AbortController();
    Promise.all([
      fetch(`${API}/collab/groups/${encodeURIComponent(activeGroup)}/plans`, { headers: { Authorization: `Bearer ${token}` }, signal: ctrl.signal }).then(r => r.json()),
      fetch(`${API}/collab/groups/${encodeURIComponent(activeGroup)}/tasks`, { headers: { Authorization: `Bearer ${token}` }, signal: ctrl.signal }).then(r => r.json()),
    ]).then(([pr, tr]) => {
      setGroupPlans(pr.plans || []);
      setGroupTasks(tr.tasks || []);
    }).catch(() => {});
    return () => ctrl.abort();
  }, [showCollab, token, activeGroup]);

  const loadGroupDetails = async (g: string) => {
    setActiveGroup(g);
    const [pr, tr] = await Promise.all([
      fetch(`${API}/collab/groups/${encodeURIComponent(g)}/plans`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`${API}/collab/groups/${encodeURIComponent(g)}/tasks`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]);
    setGroupPlans(pr.plans || []); setGroupTasks(tr.tasks || []);
  };

  const applyEvidenceMetadata = useCallback((d: {
    teaching_evidence?: TeachingEvidence[];
    generated_blocks?: GeneratedBlock[];
    missing_evidence?: string[];
  }) => {
    if (d.teaching_evidence) {
      setTeachingEvidence(prev => {
        const map = new Map<string, TeachingEvidence>();
        [...prev, ...(d.teaching_evidence || [])].forEach(item => {
          if (item.id) map.set(item.id, item);
        });
        return Array.from(map.values());
      });
    }
    if (d.generated_blocks) {
      setGeneratedBlocks(prev => {
        const map = new Map<string, GeneratedBlock>();
        [...prev, ...(d.generated_blocks || [])].forEach(item => {
          if (item.id) map.set(item.id, item);
        });
        return Array.from(map.values());
      });
    }
    if (d.missing_evidence) {
      setMissingEvidence(prev => Array.from(new Set([...prev, ...(d.missing_evidence || [])])));
    }
  }, []);

  const refreshRecordMetadata = useCallback(async (id: string) => {
    if (!id) return;
    const res = await fetch(`${API}/history/${id}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const d = await res.json();
    setTeachingEvidence(d.teaching_evidence || []);
    setGeneratedBlocks(d.generated_blocks || []);
    setMissingEvidence(d.missing_evidence || []);
  }, [token]);

  const openEvidenceDetail = useCallback(async (item: TeachingEvidence) => {
    try {
      const res = await fetch(`${API}/evidence/${encodeURIComponent(item.id)}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        setSelectedEvidence(await res.json());
        return;
      }
    } catch {}
    setSelectedEvidence(item);
  }, [token]);

  const loadHistoryDetail = async (id: string, lesson: string) => {
    try {
      const res = await fetch(`${API}/history/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setLesson(lesson);
        setExamAnalysis(d.exam_analysis || "");
        setPeerAnalysis(d.peer_analysis || "");
        setLessonPlan(d.lesson_plan || "");
        setTeachingGuide(d.teaching_guide || "");
        setLessonMindmap(d.lesson_mindmap_mermaid || "");
        setMethodMindmap(d.method_mindmap_mermaid || "");
        setTeachingEvidence(d.teaching_evidence || []);
        setGeneratedBlocks(d.generated_blocks || []);
        setMissingEvidence(d.missing_evidence || []);
        setSelectedEvidence(null);
        setMindmapError("");
        setMindmapSaveStatus("");
        setActiveTab("plan");
        setShowHistory(false);
      }
    } catch { }
  };

  // Generate
  const handleGenerate = useCallback(async () => {
    if (!lesson.trim()) { setError("请选择课题"); return; }
    setError(""); setLoading(true); setGenerationStartedAt(Date.now()); setGenerationPhase("正在准备");
    setExamAnalysis(""); setPeerAnalysis(""); setLessonPlan(""); setTeachingGuide("");
    setTeachingEvidence([]); setGeneratedBlocks([]); setMissingEvidence([]); setSelectedEvidence(null);
    setLessonMindmap(""); setMethodMindmap(""); setMindmapError(""); setMindmapSaveStatus("");
    setRevisionHistory([]); setRevisionInput(""); setActiveTab("plan");
    try {
      const res = await fetch(`${API}/generate/stream`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ grade, lesson, requirements, class_hours: classHours, semester }),
      });
      if (!res.ok) {
        let detail = "生成失败";
        try { const d = await res.json(); detail = d.detail || detail; } catch {}
        throw new Error(detail);
      }
      if (!res.body) throw new Error("浏览器不支持流式响应");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let gotDone = false;
      let generatedRecordId = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          const msg = parseSseBlock(block);
          if (!msg) continue;
          if (msg.event === "status") {
            setGenerationPhase(String(msg.data.message || "正在生成"));
          }
          if (msg.event === "token") {
            const text = String(msg.data.text || "");
            if (text) setLessonPlan(prev => prev + text);
          }
          if (msg.event === "done") {
            generatedRecordId = String(msg.data.record_id || "");
            setLastPlanId(generatedRecordId);
            if (Array.isArray(msg.data.missing_evidence)) {
              setMissingEvidence(msg.data.missing_evidence.map(String));
            }
            gotDone = true;
          }
          if (msg.event === "error") {
            throw new Error(String(msg.data.detail || "生成失败"));
          }
        }
      }
      if (!gotDone) throw new Error("生成连接中断，请重试");
      if (generatedRecordId) await refreshRecordMetadata(generatedRecordId);
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    finally { setLoading(false); setGenerationStartedAt(null); setGenerationPhase(""); }
  }, [grade, lesson, requirements, classHours, semester, token, refreshRecordMetadata]);

  const handleGenerateSection = useCallback(async (section: AuxSection) => {
    if (!lesson.trim()) { setError("请选择课题"); return; }
    if (section === "guide" && !lessonPlan.trim()) { setError("请先生成教案"); return; }
    setError("");
    setSectionLoading(section);
    const endpoint = section === "exam" ? "exam" : section === "peer" ? "peer" : "guide";
    try {
      const res = await fetch(`${API}/generate/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          grade, lesson, requirements, class_hours: classHours, semester,
          record_id: lastPlanId,
          lesson_plan: lessonPlan,
          exam_analysis: examAnalysis,
          peer_analysis: peerAnalysis,
        }),
      });
      if (!res.ok) {
        let detail = "生成失败";
        try { const d = await res.json(); detail = d.detail || detail; } catch {}
        throw new Error(detail);
      }
      const d = await res.json();
      if (section === "exam") setExamAnalysis(d.exam_analysis || "");
      if (section === "peer") setPeerAnalysis(d.peer_analysis || "");
      if (section === "guide") setTeachingGuide(d.teaching_guide || "");
      applyEvidenceMetadata(d);
      if (lastPlanId) await refreshRecordMetadata(lastPlanId);
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    } finally {
      setSectionLoading("");
    }
  }, [grade, lesson, requirements, classHours, semester, token, lastPlanId, lessonPlan, examAnalysis, peerAnalysis, applyEvidenceMetadata, refreshRecordMetadata]);

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
      if (!res.ok) {
        let detail = "修改失败";
        try { const d = await res.json(); detail = d.detail || detail; } catch {}
        throw new Error(detail);
      }
      const d = await res.json();
      setRevisionHistory(prev => [...prev, revisionInput, "修改完成"]);
      setLessonPlan(d.lesson_plan); setRevisionInput(""); setActiveTab("plan");
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    finally { setRevising(false); }
  }, [revisionInput, revisionHistory, lessonPlan, token]);

  // Unit plan
  const handleUnitPlan = async () => {
    setLoadingUnit(true); setUnitPlan("");
    try {
      const res = await fetch(`${API}/unit-plan`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ grade, unit: unitName || "第一单元", semester }),
      });
      if (!res.ok) throw new Error("生成失败");
      const d = await res.json(); setUnitPlan(d.unit_plan || "");
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    finally { setLoadingUnit(false); }
  };

  // Mindmap
  const handleGenerateMindmap = useCallback(async () => {
    if (!lessonPlan) { setMindmapError("请先生成教案，再生成思维导图"); return; }
    setMindmapError(""); setMindmapLoading(true);
    setLessonMindmap(""); setMethodMindmap("");
    try {
      const res = await fetch(`${API}/mindmap/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          grade, lesson,
          lesson_plan: lessonPlan,
          teaching_guide: teachingGuide,
          analysis: examAnalysis,
          peer_reference: peerAnalysis,
        }),
      });
      if (!res.ok) {
        let detail = "思维导图生成失败";
        try { const d = await res.json(); detail = d.detail || detail; } catch {}
        if (res.status === 401) throw new Error("登录已过期，请重新登录");
        if (res.status === 429) throw new Error("请求过于频繁，请稍后再试");
        throw new Error(detail);
      }
      const d = await res.json();
      const lessonMm = d.lesson_mindmap_mermaid || "";
      const methodMm = d.method_mindmap_mermaid || "";
      setLessonMindmap(lessonMm);
      setMethodMindmap(methodMm);

      // 自动保存到历史记录
      if (lastPlanId && (lessonMm || methodMm)) {
        setMindmapSaveStatus("");
        try {
          const saveRes = await fetch(`${API}/history/${lastPlanId}/mindmap`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ lesson_mindmap_mermaid: lessonMm, method_mindmap_mermaid: methodMm }),
          });
          if (!saveRes.ok) setMindmapSaveStatus("导图已生成，但保存到历史记录失败");
        } catch { setMindmapSaveStatus("导图已生成，但保存到历史记录失败"); }
      }
    } catch (e: unknown) { setMindmapError(getErrorMessage(e)); }
    finally { setMindmapLoading(false); }
  }, [lessonPlan, teachingGuide, examAnalysis, peerAnalysis, grade, lesson, token, lastPlanId]);

  const copyMermaidSource = (code: string) => {
    navigator.clipboard.writeText(code).then(
      () => alert("已复制"),
      () => alert("复制失败，请手动选择源码")
    );
  };

  const downloadMermaidSource = (code: string, suffix: string) => {
    if (!code.trim()) return;
    const safeLesson = lesson.replace(/[\\/:*?"<>|]/g, "");
    const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safeLesson}_${suffix}.mmd`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Reflection
  const handleReflect = async () => {
    setLoadingReflect(true); setReflection("");
    try {
      const res = await fetch(`${API}/reflect`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ lesson, lesson_plan: lessonPlan }),
      });
      if (!res.ok) throw new Error("生成失败");
      const d = await res.json(); setReflection(d.reflection || "");
    } catch (e: unknown) { setError(getErrorMessage(e)); }
    finally { setLoadingReflect(false); }
  };

  const selectLesson = useCallback((g: string, s: string, l: string) => {
    setGrade(g);
    setSemester(s.startsWith("下") ? "下" : "上");
    setLesson(l);
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
    { key: "exam", label: "考点", icon: "🎯" }, { key: "peer", label: "同行", icon: "👥" },
    { key: "plan", label: "教案", icon: "📝" }, { key: "guide", label: "辅导", icon: "🎓" },
    { key: "lessonMindmap", label: "教案导图", icon: "🗺️" }, { key: "methodMindmap", label: "备课方法", icon: "🧠" },
  ];
  const normativeEvidence = teachingEvidence.filter(item => item.source_role === "normative");
  const methodEvidence = teachingEvidence.filter(item => item.source_role === "method_case");
  const insufficientBlocks = generatedBlocks.filter(item => item.evidence_status === "insufficient");
  const evidenceById = useMemo(() => {
    const map = new Map<string, TeachingEvidence>();
    teachingEvidence.forEach(item => map.set(item.id, item));
    return map;
  }, [teachingEvidence]);
  const selectedBboxStyle = selectedEvidence ? bboxOverlayStyle(selectedEvidence) : null;

  // ---- SETUP WIZARD ----
  if (needsSetup) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-amber-50">
        <div className="bg-white rounded-xl shadow-lg border border-amber-100 p-8 w-full max-w-md">
          <div className="text-center mb-6">
            <span className="text-4xl select-none">📖</span>
            <h1 className="text-xl font-bold text-amber-800 mt-2">LeKai教案知识库</h1>
            <p className="text-sm text-amber-600 mt-1">首次启动 · 初始化设置</p>
          </div>

          {/* Step indicator */}
          <div className="flex justify-center gap-2 mb-6">
            {[1,2,3].map(s => (
              <div key={s} className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${setupStep >= s ? "bg-amber-600 text-white" : "bg-gray-200 text-gray-500"}`}>{s}</div>
            ))}
          </div>

          {setupStep === 1 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📡 WiFi 网络设置</h3>
              <p className="text-xs text-gray-500 mb-3">盒子需要联网才能使用AI功能。请连接学校的WiFi。</p>
              <button onClick={async () => {
                setWifiScanning(true);
                const d = await fetch("/api/setup/wifi-scan").then(r => r.json());
                setWifiList(d.networks || []);
                setWifiScanning(false);
              }} disabled={wifiScanning} className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm mb-3 hover:bg-blue-700 disabled:bg-blue-300">
                {wifiScanning ? "📡 扫描中..." : "📡 扫描WiFi"}
              </button>
              {wifiList.length > 0 && (
                <div className="max-h-40 overflow-y-auto border rounded-lg mb-3">
                  {wifiList.map(w => (
                    <button key={w.ssid} onClick={() => setWifiSSID(w.ssid)}
                      className={`w-full text-left px-3 py-2 text-xs border-b hover:bg-amber-50 ${wifiSSID === w.ssid ? "bg-amber-100" : ""}`}>
                      {w.ssid} <span className="text-gray-400">{w.signal > 60 ? "📶📶📶" : w.signal > 30 ? "📶📶" : "📶"}</span>
                    </button>
                  ))}
                </div>
              )}
              {wifiSSID && (
                <>
                  <input type="password" value={wifiPass} onChange={e => setWifiPass(e.target.value)}
                    placeholder="WiFi密码（无密码留空）" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3" />
                  <button onClick={async () => {
                    try {
                      const r = await fetch("/api/setup/wifi-connect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ssid: wifiSSID, password: wifiPass }) });
                      if (r.ok) { setSetupStep(2); setSetupError(""); }
                      else { const d = await r.json(); setSetupError(d.detail); }
                    } catch { setSetupError("连接失败"); }
                  }} className="w-full bg-green-600 text-white py-2 rounded-lg text-sm hover:bg-green-700 mb-2">
                    连接 {wifiSSID}
                  </button>
                  <button onClick={() => setSetupStep(2)} className="w-full text-xs text-gray-400 hover:text-gray-600">跳过（已插网线）</button>
                </>
              )}
              {!wifiSSID && wifiList.length === 0 && !wifiScanning && (
                <button onClick={() => setSetupStep(2)} className="w-full text-xs text-gray-400 hover:text-gray-600">跳过WiFi设置（已插网线）</button>
              )}
            </div>
          )}

          {setupStep === 2 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">🔐 设置管理员密码</h3>
              <p className="text-xs text-gray-500 mb-3">这是您以后登录系统用的账号和密码。</p>
              <input type="password" value={setupAdminPass} onChange={e => setSetupAdminPass(e.target.value)}
                placeholder="管理员密码（至少4位）" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3" />
              <button onClick={() => {
                if (setupAdminPass.length < 4) { setSetupError("密码至少4位"); return; }
                setSetupStep(3); setSetupError("");
              }} className="w-full bg-amber-600 text-white py-2 rounded-lg text-sm hover:bg-amber-700">下一步</button>
            </div>
          )}

          {setupStep === 3 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">🔑 DeepSeek API Key</h3>
              <p className="text-xs text-gray-500 mb-3">系统使用DeepSeek大模型生成教案。请在 platform.deepseek.com 注册获取Key。</p>
              <input type="text" value={setupApiKey} onChange={e => setSetupApiKey(e.target.value)}
                placeholder="sk-xxxxxxxx" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 font-mono" />
              <button onClick={async () => {
                setSetupError("");
                try {
                  const r = await fetch("/api/setup/complete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: setupAdminPass, api_key: setupApiKey }) });
                  if (r.ok) { setNeedsSetup(false); }
                  else { const d = await r.json(); setSetupError(d.detail); }
                } catch { setSetupError("初始化失败，请检查网络"); }
              }} className="w-full bg-amber-600 text-white py-2 rounded-lg text-sm hover:bg-amber-700 mb-3">完成初始化</button>
            </div>
          )}

          {setupError && <div className="text-sm text-red-600 text-center mt-3">{setupError}</div>}
        </div>
      </div>
    );
  }

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
            登录
          </button>
          {authError && <div className="text-sm text-red-600 text-center mb-3">{authError}</div>}
          <p className="text-xs text-gray-400 text-center">账号由管理员创建，请联系教研组长</p>
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
            <span className="text-xs text-gray-400 hidden sm:inline">K9-AI v1.0</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadHistory} className="text-xs text-gray-500 hover:text-amber-700 px-2 py-1 rounded">📋 历史</button>
            <button onClick={() => { setShowCollab(!showCollab); if (!showCollab) loadCollab(); }} className="text-xs text-gray-500 hover:text-blue-700 px-2 py-1 rounded">👥 教研</button>
            {(userRole === "admin" || userRole === "reviewer") && (
              <a href="/admin" className="text-xs text-amber-600 hover:text-amber-800 px-2 py-1 rounded font-medium">⚙️ 管理</a>
            )}
            <span className="text-xs text-gray-400">{username}{userRole === "admin" ? "(管理员)" : userRole === "reviewer" ? "(教研组长)" : ""}</span>
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
                <select value={semester.startsWith("下") ? "下" : "上"} onChange={e => setSemester(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="上">上册</option><option value="下">下册</option>
                </select>
                <select value={classHours} onChange={e => setClassHours(e.target.value)} className="border border-gray-300 rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-amber-400 outline-none">
                  <option value="1">1课时</option><option value="2">2课时</option><option value="3">3课时</option>
                </select>
                <input type="text" value={lesson} onChange={e => setLesson(e.target.value)} placeholder="课题" className="border border-gray-300 rounded-lg px-3 py-1 text-sm focus:ring-2 focus:ring-amber-400 outline-none w-32" />
                <button onClick={handleGenerate} disabled={loading}
                  className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 text-white font-medium px-4 py-1 rounded-lg text-sm transition-colors">
                  {loading ? `生成中 ${generationElapsed}s` : "生成教案"}
                </button>
                <input type="text" value={unitName} onChange={e => setUnitName(e.target.value)}
                  placeholder="单元名" className="border border-gray-300 rounded-lg px-2 py-1 text-sm w-28" />
                <button onClick={handleUnitPlan} disabled={loadingUnit}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium px-4 py-1 rounded-lg text-sm transition-colors">
                  {loadingUnit ? "规划中..." : "单元规划"}
                </button>
              </div>
              <textarea value={requirements} onChange={e => setRequirements(e.target.value)} placeholder="教学要求（可选）" rows={1}
                className="w-full border border-gray-300 rounded-lg px-3 py-1 text-sm focus:ring-2 focus:ring-amber-400 outline-none resize-none" />
              {loading && (
                <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-sm text-amber-800">
                  {generationPhase || "正在流式生成教案"}，正文会逐步显示。考点分析、同行参考、辅导说明可在教案生成后按需生成。
                </div>
              )}
              {error && <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">{error}</div>}
            </div>

            {/* Results */}
            {(examAnalysis || peerAnalysis || lessonPlan || teachingGuide) && (
              <div className="bg-white rounded-xl shadow-sm border border-amber-100 overflow-hidden mb-4">
                <div className="flex border-b border-gray-200 overflow-x-auto">
                  {TABS.map(t => {
                    const has = (t.key === "exam" && (lessonPlan || examAnalysis)) || (t.key === "peer" && (lessonPlan || peerAnalysis)) || (t.key === "plan" && lessonPlan) || (t.key === "guide" && (lessonPlan || teachingGuide)) || (t.key === "lessonMindmap" && lessonPlan) || (t.key === "methodMindmap" && lessonPlan);
                    return (
                      <button key={t.key} onClick={() => setActiveTab(t.key)} disabled={!has}
                        className={`flex-1 py-2 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === t.key ? "text-amber-700 border-b-2 border-amber-500 bg-amber-50" : has ? "text-gray-500 hover:text-gray-700" : "text-gray-300 cursor-not-allowed"}`}>
                        <span className="mr-1">{t.icon}</span>{t.label}
                      </button>
                    );
                  })}
                </div>
                <div className="p-4 max-h-[55vh] overflow-y-auto">
                  {(activeTab === "lessonMindmap" || activeTab === "methodMindmap") ? (
                    <MindmapTabContent
                      code={activeTab === "lessonMindmap" ? lessonMindmap : methodMindmap}
                      loading={mindmapLoading}
                      error={mindmapError}
                      hasPlan={!!lessonPlan}
                      onGenerate={handleGenerateMindmap}
                      saveStatus={mindmapSaveStatus}
                      onCopy={() => copyMermaidSource(activeTab === "lessonMindmap" ? lessonMindmap : methodMindmap)}
                      onDownload={() => downloadMermaidSource(
                        activeTab === "lessonMindmap" ? lessonMindmap : methodMindmap,
                        activeTab === "lessonMindmap" ? "教案导图" : "备课方法导图"
                      )}
                    />
                  ) : (activeTab === "exam" || activeTab === "peer" || activeTab === "guide") && !tabContent() ? (
                    <AuxSectionEmpty
                      section={activeTab}
                      loading={sectionLoading === activeTab}
                      disabled={!!sectionLoading}
                      onGenerate={() => handleGenerateSection(activeTab)}
                    />
                  ) : (
                    <div className="prose prose-amber prose-sm max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{tabContent()}</ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            )}

            {lessonPlan && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">依据与参考</h3>
                    <p className="text-xs text-gray-500">规范材料用于教学判断，案例材料只作为参考做法。</p>
                  </div>
                  {insufficientBlocks.length > 0 && (
                    <span className="text-xs px-2 py-1 rounded bg-red-50 text-red-700 border border-red-100">
                      {insufficientBlocks.length} 处依据不足
                    </span>
                  )}
                </div>
                {missingEvidence.length > 0 && (
                  <div className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    {missingEvidence.join("；")}
                  </div>
                )}
                {generatedBlocks.length > 0 && (
                  <div className="mb-3 rounded border border-slate-100 bg-slate-50 p-3">
                    <div className="text-xs font-semibold text-slate-700 mb-2">模块依据状态</div>
                    <div className="space-y-2">
                      {generatedBlocks.map(block => (
                        <div key={block.id} className="rounded bg-white border border-slate-100 px-3 py-2 text-xs">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-slate-800">{BLOCK_TYPE_LABEL[block.block_type] || block.block_type}</span>
                            <span className={`px-2 py-0.5 rounded ${
                              block.evidence_status === "supported" ? "bg-emerald-50 text-emerald-700" :
                              block.evidence_status === "insufficient" ? "bg-red-50 text-red-700" :
                              "bg-gray-50 text-gray-500"
                            }`}>
                              {block.evidence_status === "supported" ? "有依据" : block.evidence_status === "insufficient" ? "依据不足" : "无需依据"}
                            </span>
                          </div>
                          {(block.evidence_ids.length > 0 || block.reference_ids.length > 0) && (
                            <div className="flex gap-1 flex-wrap mt-2">
                              {block.evidence_ids.map(id => {
                                const item = evidenceById.get(id);
                                if (!item) return null;
                                return (
                                  <button key={id} onClick={() => openEvidenceDetail(item)}
                                    className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 hover:bg-emerald-100">
                                    依据：{DOC_TYPE_LABEL[item.doc_type] || item.doc_type}
                                  </button>
                                );
                              })}
                              {block.reference_ids.map(id => {
                                const item = evidenceById.get(id);
                                if (!item) return null;
                                return (
                                  <button key={id} onClick={() => openEvidenceDetail(item)}
                                    className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 hover:bg-blue-100">
                                    参考：{DOC_TYPE_LABEL[item.doc_type] || item.doc_type}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="rounded border border-emerald-100 bg-emerald-50/60 p-3">
                    <div className="text-xs font-semibold text-emerald-800 mb-2">规范依据</div>
                    {normativeEvidence.length === 0 ? (
                      <div className="text-xs text-emerald-700">暂无可追溯规范依据。请补充教材、课标、考纲或单元目标。</div>
                    ) : normativeEvidence.slice(0, 8).map(item => (
                      <button key={item.id} onClick={() => openEvidenceDetail(item)}
                        className="block w-full text-left text-xs bg-white border border-emerald-100 rounded px-2 py-2 mb-2 hover:border-emerald-300">
                        <div className="font-medium text-emerald-900">依据：{DOC_TYPE_LABEL[item.doc_type] || item.doc_type}</div>
                        <div className="text-gray-600 truncate">{item.doc_title || "知识库材料"}{item.page_num ? ` · 第${item.page_num}页` : ""}</div>
                      </button>
                    ))}
                  </div>
                  <div className="rounded border border-blue-100 bg-blue-50/60 p-3">
                    <div className="text-xs font-semibold text-blue-800 mb-2">参考做法</div>
                    {methodEvidence.length === 0 ? (
                      <div className="text-xs text-blue-700">暂无方法参考。可补充教学设计指导、老教师教案或本校案例。</div>
                    ) : methodEvidence.slice(0, 8).map(item => (
                      <button key={item.id} onClick={() => openEvidenceDetail(item)}
                        className="block w-full text-left text-xs bg-white border border-blue-100 rounded px-2 py-2 mb-2 hover:border-blue-300">
                        <div className="font-medium text-blue-900">参考：{DOC_TYPE_LABEL[item.doc_type] || item.doc_type}</div>
                        <div className="text-gray-600 truncate">{item.doc_title || "知识库材料"}{item.page_num ? ` · 第${item.page_num}页` : ""}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {selectedEvidence && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">
                      {selectedEvidence.source_role === "normative" ? "依据" : "参考"}：{DOC_TYPE_LABEL[selectedEvidence.doc_type] || selectedEvidence.doc_type}
                    </h3>
                    <p className="text-xs text-gray-500">
                      {selectedEvidence.doc_title || "知识库材料"}
                      {selectedEvidence.page_num ? ` · 第${selectedEvidence.page_num}页` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedEvidence.dee_url && (
                      <a href={selectedEvidence.dee_url} target="_blank" rel="noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800">
                        打开原文
                      </a>
                    )}
                    <button onClick={() => setSelectedEvidence(null)} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
                  </div>
                </div>
                {(selectedEvidence.page_width || selectedEvidence.page_height || (selectedEvidence.bbox || []).length > 0) && (
                  <div className="mt-2 text-xs text-slate-500">
                    原文定位：page={selectedEvidence.page_num || 0}，bbox=[{(selectedEvidence.bbox || []).join(", ")}]
                  </div>
                )}
                {selectedEvidence.page_image_url && (
                  <div className="mt-3 overflow-auto rounded border border-slate-200 bg-slate-100 p-2">
                    <div className="relative mx-auto max-w-full" style={{ width: selectedEvidence.page_width ? `${selectedEvidence.page_width}px` : "100%" }}>
                      {/* DEE page images can come from an internal appliance URL that is not known at build time. */}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={selectedEvidence.page_image_url} alt="原文页" className="block h-auto max-w-full" />
                      {selectedBboxStyle && (
                        <div className="absolute border-2 border-red-500 bg-red-400/20 shadow-[0_0_0_9999px_rgba(0,0,0,0.08)]" style={selectedBboxStyle} />
                      )}
                    </div>
                  </div>
                )}
                <div className="mt-3 rounded border border-slate-100 bg-slate-50 p-3 text-sm text-slate-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {selectedEvidence.content}
                </div>
              </div>
            )}

            {/* Mindmap standalone section (for regenerate)} */}
            {(lessonMindmap || methodMindmap || mindmapError) && lessonPlan && (
              <div className="bg-white rounded-xl shadow-sm border border-indigo-100 p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-indigo-800">🧠 思维导图</h3>
                    <p className="text-xs text-gray-500">重新生成会覆盖当前导图</p>
                  </div>
                  <button onClick={handleGenerateMindmap} disabled={mindmapLoading}
                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white text-xs px-3 py-1 rounded transition-colors">
                    {mindmapLoading ? "生成中..." : "重新生成"}
                  </button>
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

            {/* Unit Plan */}
            {unitPlan && (
              <div className="bg-white rounded-xl shadow-sm border border-blue-100 p-5 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-base font-bold text-blue-800">📐 单元整体规划</h2>
                  <button onClick={() => setUnitPlan("")} className="text-xs text-gray-400 hover:text-gray-600">✕</button>
                </div>
                <div className="prose prose-sm max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{unitPlan}</ReactMarkdown></div>
              </div>
            )}

            {/* Collab Panel */}
            {showCollab && (
              <div className="bg-white rounded-xl shadow-sm border border-blue-100 p-5 mb-4">
                <h2 className="text-base font-bold text-blue-800 mb-3">👥 教研协作</h2>
                <div className="flex gap-2 mb-3">
                  <input value={newGroupName} onChange={e => setNewGroupName(e.target.value)} placeholder="新教研组名称" className="border border-gray-300 rounded px-2 py-1 text-xs flex-1" />
                  <button onClick={async () => {
                    await fetch(`${API}/collab/groups/create`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ name: newGroupName }) });
                    setNewGroupName(""); loadCollab();
                  }} className="bg-blue-600 text-white text-xs px-3 py-1 rounded">创建</button>
                </div>
                {groups.length === 0 && <div className="text-xs text-gray-400">暂无教研组，创建一个吧</div>}
                <div className="flex gap-1 flex-wrap mb-3">
                  {groups.map((g) => (
                    <button key={g.name} onClick={() => { loadGroupDetails(g.name); }}
                      className={`text-xs px-2 py-1 rounded ${activeGroup === g.name ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-blue-50"}`}>
                      {g.name} ({g.members?.length || 0}人)
                    </button>
                  ))}
                  {!myGroups.includes(activeGroup) && activeGroup && (
                    <button onClick={async () => {
                      await fetch(`${API}/collab/groups/join`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ name: activeGroup }) });
                      loadCollab();
                    }} className="text-xs text-blue-600 underline">加入</button>
                  )}
                </div>
                {activeGroup && (
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs font-semibold text-gray-600">共享教案 ({groupPlans.length})</span>
                      <button onClick={async () => {
                        await fetch(`${API}/collab/tasks/assign`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ group: activeGroup, assigned_to: username, lesson: lesson || "待定" }) });
                        loadGroupDetails(activeGroup);
                      }} className="text-xs text-blue-600 underline">分配备课任务</button>
                    </div>
                    {groupPlans.map((p, i) => (
                      <div key={i} className="text-xs border-b border-gray-100 py-1">
                        <span className="font-medium">{p.shared_by}</span> · 《{p.lesson}》{p.grade}
                        <span className="text-gray-400 ml-2">{p.timestamp?.slice(0, 16)}</span>
                        {p.comments?.map((c, j) => (
                          <div key={j} className="ml-4 text-gray-500">{c.username}: {c.text}</div>
                        ))}
                        <div className="flex gap-1 mt-1">
                          <input value={collabComment} onChange={e => setCollabComment(e.target.value)} placeholder="评论..." className="border border-gray-200 rounded px-1 py-0 text-xs flex-1" />
                          <button onClick={async () => {
                            await fetch(`${API}/collab/comment`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ group: activeGroup, plan_index: i, text: collabComment }) });
                            setCollabComment(""); loadGroupDetails(activeGroup);
                          }} className="text-xs bg-gray-200 px-1 rounded">发送</button>
                        </div>
                      </div>
                    ))}
                    <div className="mt-3 border-t border-gray-100 pt-2">
                      <div className="text-xs font-semibold text-gray-600 mb-1">备课任务 ({groupTasks.length})</div>
                      {groupTasks.length === 0 && <div className="text-xs text-gray-400">暂无任务</div>}
                      {groupTasks.map((task, i) => (
                        <div key={i} className="flex items-center justify-between gap-2 text-xs border-b border-gray-50 py-1">
                          <div>
                            <span className={task.done || task.status === "done" ? "line-through text-gray-400" : "text-gray-700"}>《{task.lesson}》</span>
                            <span className="text-gray-400 ml-2">指派给 {task.assigned_to}</span>
                          </div>
                          {!(task.done || task.status === "done") && (
                            <button onClick={async () => {
                              await fetch(`${API}/collab/tasks/complete`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ group: activeGroup, task_index: i }) });
                              loadGroupDetails(activeGroup);
                            }} className="text-blue-600 hover:underline">完成</button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Reflection */}
            {reflection && (
              <div className="bg-white rounded-xl shadow-sm border border-green-100 p-5 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-base font-bold text-green-800">📝 课后反思引导</h2>
                  <button onClick={() => setReflection("")} className="text-xs text-gray-400">✕</button>
                </div>
                <div className="prose prose-sm max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{reflection}</ReactMarkdown></div>
              </div>
            )}

            {/* Export */}
            {lessonPlan && lastPlanId && (
              <div className="bg-white rounded-xl shadow-sm border border-blue-100 p-4 mb-4">
                <h3 className="text-sm font-semibold text-blue-800 mb-2">📥 导出教案</h3>
                <div className="flex gap-2">
                  <button onClick={async () => {
                    try {
                      const r = await fetch(`${API}/export/${lastPlanId}?format=md`, { headers: { Authorization: `Bearer ${token}` } });
                      if (!r.ok) { alert("导出失败"); return; }
                      const blob = await r.blob();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a"); a.href = url; a.download = `${lesson}_教案.md`; a.click();
                      URL.revokeObjectURL(url);
                    } catch { alert("导出失败：网络错误"); }
                  }} className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">下载 MD</button>
                  <button onClick={async () => {
                    try {
                      const r = await fetch(`${API}/export/${lastPlanId}?format=docx`, { headers: { Authorization: `Bearer ${token}` } });
                      if (!r.ok) { alert("导出失败"); return; }
                      const blob = await r.blob();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a"); a.href = url; a.download = `${lesson}_教案.docx`; a.click();
                      URL.revokeObjectURL(url);
                    } catch { alert("导出失败：网络错误"); }
                  }} className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">下载 DOCX</button>
                </div>
                {(lessonMindmap || methodMindmap) && (
                  <div className="flex gap-2 mt-2">
                    <button onClick={async () => {
                      try {
                        const r = await fetch(`${API}/export/${lastPlanId}?format=md&include_mindmap=true`, { headers: { Authorization: `Bearer ${token}` } });
                        if (!r.ok) { alert("导出失败"); return; }
                        const blob = await r.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a"); a.href = url; a.download = `${lesson}_教案_含导图.md`; a.click();
                        URL.revokeObjectURL(url);
                      } catch { alert("导出失败：网络错误"); }
                    }} className="text-xs bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700">下载 MD（含导图）</button>
                    <button onClick={async () => {
                      try {
                        const r = await fetch(`${API}/export/${lastPlanId}?format=docx&include_mindmap=true`, { headers: { Authorization: `Bearer ${token}` } });
                        if (!r.ok) { alert("导出失败"); return; }
                        const blob = await r.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a"); a.href = url; a.download = `${lesson}_教案_含导图.docx`; a.click();
                        URL.revokeObjectURL(url);
                      } catch { alert("导出失败：网络错误"); }
                    }} className="text-xs bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700">下载 DOCX（含导图）</button>
                  </div>
                )}
              </div>
            )}

            {/* Feedback */}
            {lessonPlan && lastPlanId && (
              <div className="bg-white rounded-xl shadow-sm border border-purple-100 p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-purple-800">⭐ 教案评分</h3>
                    <p className="text-xs text-gray-500">评分会反哺检索系统，让后续推荐更精准</p>
                  </div>
                  <div className="flex items-center gap-1">
                    {[1,2,3,4,5].map(s => (
                      <button key={s} onClick={async () => {
                        try {
                          const r = await fetch(`${API}/feedback`, {
                            method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                            body: JSON.stringify({ plan_id: lastPlanId, grade, lesson, rating: s }),
                          });
                          if (r.ok) setFeedbackRating(s);
                        } catch { /* 静默失败 */ }
                      }} className={`text-xl transition-colors ${feedbackRating >= s ? "text-purple-500" : "text-gray-300 hover:text-purple-300"}`}>
                        ★
                      </button>
                    ))}
                  </div>
                </div>
                {feedbackRating > 0 && <p className="text-xs text-purple-600 mt-2">已评分 {feedbackRating} 星，感谢反馈！</p>}
              </div>
            )}

            {/* Submit Review */}
            {lessonPlan && lastPlanId && (
              <div className="bg-white rounded-xl shadow-sm border border-green-100 p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-green-800">✅ 提交校本审核</h3>
                    <p className="text-xs text-gray-500">提交后教研组长将审核此教案</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={handleReflect} disabled={loadingReflect}
                      className="bg-green-100 text-green-800 text-sm px-3 py-1 rounded hover:bg-green-200">
                      {loadingReflect ? "生成中..." : "📝 课后反思"}
                    </button>
                    <button onClick={async () => {
                      try {
                        const res = await fetch(`${API}/review/submit`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ record_id: lastPlanId }) });
                        if (res.ok) alert("已提交审核！"); else alert("提交失败");
                      } catch { alert("提交失败"); }
                    }} className="bg-green-600 text-white text-sm px-3 py-1 rounded hover:bg-green-700">📤 提交审核</button>
                  </div>
                </div>
              </div>
            )}

            {/* Evaluate Plan */}
            <div className="bg-white rounded-xl shadow-sm border border-teal-100 p-4 mb-4">
              <h3 className="text-sm font-semibold text-teal-800 mb-2">🔍 教案评价</h3>
              <p className="text-xs text-gray-500 mb-2">上传你的教案，AI对照优秀教案给出评价和改进建议</p>
              <input type="file" accept=".md,.txt,.docx" onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const form = new FormData();
                form.append("file", f);
                setEvaluation(""); setEvaluating(true);
                try {
                  const res = await fetch(`${API}/evaluate`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
                  const d = await res.json();
                  setEvaluation(d.evaluation || "");
                } catch { setError("评价失败"); }
                finally { setEvaluating(false); e.target.value = ""; }
              }} className="text-xs" />
              {evaluating && <p className="text-xs text-gray-400 mt-2">正在分析...</p>}
              {evaluation && (
                <div className="mt-3 bg-teal-50 rounded-lg p-3 max-h-80 overflow-y-auto">
                  <div className="prose prose-teal prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{evaluation}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>

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

function AuxSectionEmpty({
  section, loading, disabled, onGenerate,
}: {
  section: AuxSection; loading: boolean; disabled: boolean; onGenerate: () => void;
}) {
  const meta = {
    exam: { title: "考点分析", desc: "生成本课常考字词、阅读理解、仿写迁移和易错点。", action: "生成考点分析" },
    peer: { title: "同行参考", desc: "从知识库提取其他老师的教学思路、环节设计和可借鉴做法。", action: "生成同行参考" },
    guide: { title: "辅导说明", desc: "基于当前教案生成上课建议、亮点分析和避坑提示。", action: "生成辅导说明" },
  }[section];
  return (
    <div className="text-center py-10">
      <div className="text-sm font-semibold text-gray-700 mb-2">{meta.title}尚未生成</div>
      <p className="text-xs text-gray-400 mb-4">{meta.desc}</p>
      <button
        onClick={onGenerate}
        disabled={disabled}
        className="bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300 text-white text-sm px-4 py-2 rounded-lg transition-colors"
      >
        {loading ? "生成中..." : meta.action}
      </button>
    </div>
  );
}

function MindmapTabContent({
  code, loading, error, hasPlan, saveStatus, onGenerate, onCopy, onDownload,
}: {
  code: string; loading: boolean; error: string; hasPlan: boolean; saveStatus: string;
  onGenerate: () => void; onCopy: () => void; onDownload: () => void;
}) {
  if (!hasPlan) {
    return <div className="text-center py-8 text-gray-400 text-sm">请先生成教案，再生成思维导图</div>;
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400 text-sm">正在生成思维导图，请稍候...</div>;
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-sm text-red-600 mb-3">思维导图生成失败：{error}</div>
        <button onClick={onGenerate} className="bg-indigo-600 text-white text-xs px-4 py-1.5 rounded hover:bg-indigo-700">重试</button>
      </div>
    );
  }

  if (!code) {
    return (
      <div className="text-center py-8">
        <div className="text-gray-400 text-sm mb-3">尚未生成思维导图</div>
        <button onClick={onGenerate} className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg transition-colors">生成思维导图</button>
      </div>
    );
  }

  return (
    <div>
      {saveStatus && <div className="text-xs text-amber-600 mb-2">{saveStatus}</div>}
      <MermaidMindmap code={code} />
      <div className="mt-4 border-t border-gray-100 pt-3">
        <button onClick={onCopy} className="text-xs text-indigo-600 hover:text-indigo-800 mr-4">📋 复制 Mermaid 源码</button>
        <button onClick={onDownload} className="text-xs text-indigo-600 hover:text-indigo-800 mr-4">⬇ 下载 Mermaid 源码</button>
        <details className="inline text-xs">
          <summary className="text-gray-500 cursor-pointer hover:text-gray-700 inline">查看 Mermaid 源码</summary>
          <pre className="mt-2 text-xs bg-gray-50 p-2 rounded border overflow-x-auto max-h-32 whitespace-pre">{code}</pre>
        </details>
      </div>
    </div>
  );
}
