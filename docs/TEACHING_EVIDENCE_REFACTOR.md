# 教案系统逻辑重构方案

## 1. 产品定位

本系统定位为校内/教研组内网教研盒子，服务约 20 位语文老师，不按大型 SaaS 设计。

核心产物是一份可下载、可修改、可直接上课使用的完整教案。系统的增强价值是让老师同时看到：

- 教案正文：能直接交付和上课。
- 规范依据：教材、课标、考纲、单元目标、考试说明、题库/考点材料。
- 方法参考：《教学设计与指导》、老教师教案、本校案例、进修校案例、教研记录。
- 备课方法解释：说明目标、重难点、活动设计为什么这样做，帮助年轻老师学习备课。

## 2. 项目内部职责边界

### 内嵌 DEE 证据层

DEE 不作为单独服务部署，而是完整融入 LeKai 语文教案系统，作为本地证据层和数据规范。它负责“原件为真”的能力：

- 保存原始文件、页面图像、页码。
- 产生 EvidenceObject / EvidencePack。
- 保留 `source_file_id`、`source_file_name`、`source_hash`、`page_num`、`page_width`、`page_height`、`bbox`。
- 在 LeKai 内提供原文页和 bbox 高亮能力。

### 教学业务层

LeKai 的教学业务层负责：

- 选课、输入教学要求。
- 分层检索规范依据与方法参考。
- 生成完整教案、考点分析、同行参考、辅导说明。
- 保存历史、结构化 block、evidence/reference 映射。
- 导出 `.md` / `.docx`，附“依据与参考附录”。
- 在前端区分展示“依据”和“参考”，并使用内嵌证据层展示原文定位和 bbox 高亮。

## 3. 教学证据模型

后端使用 `TeachingEvidence` 作为教学业务层统一证据模型，由本地索引 chunk 或导入时保留的 DEE EvidenceObject 字段转换而来。

```ts
type SourceRole = "normative" | "method_case";

interface TeachingEvidence {
  id: string;
  source_role: SourceRole;
  doc_type:
    | "textbook"
    | "curriculum_standard"
    | "exam_outline"
    | "unit_goal"
    | "exam_material"
    | "teaching_guidance"
    | "teacher_case"
    | "local_case"
    | "training_case";
  doc_title: string;
  grade?: string;
  semester?: string;
  unit?: string;
  lesson?: string;
  page_num: number;
  page_width: number;
  page_height: number;
  bbox: number[];
  content: string;
  confidence: number;
  source_file_id: string;
  source_file_name: string;
  source_hash: string;
  page_image_url?: string;
  dee_url?: string;
}
```

规则：

- `normative`：教材、课标、考纲、单元目标、考试说明、题库/考点资料。
- `method_case`：教学设计指导、老教师教案、本校案例、进修校案例、教研记录。
- `evidence_ids` 只能引用 `normative`。
- `reference_ids` 只能引用 `method_case`。
- 老教师教案和教学指导永远不能显示为“依据”，只能显示为“参考”。

## 4. 生成结果结构

教案正文继续保存 Markdown，但同时保存 block 级元数据。

```ts
interface GeneratedBlock {
  id: string;
  block_type:
    | "textbook_analysis"
    | "student_analysis"
    | "teaching_goal"
    | "key_point"
    | "exam_point"
    | "teaching_activity"
    | "homework"
    | "board_design"
    | "guidance";
  text: string;
  evidence_ids: string[];
  reference_ids: string[];
  evidence_status: "supported" | "insufficient" | "not_required";
}
```

校验规则：

- `teaching_goal`、`key_point`、`exam_point` 应尽量绑定 `normative evidence`。
- 缺少规范依据时标记 `evidence_status="insufficient"`。
- `teaching_activity` 可以吸收方法样本，但只进入 `reference_ids`。
- citation validation 必须阻止 `method_case` 混入 `evidence_ids`。

## 5. 四个业务功能

### 生成教案

- 主按钮仍为“生成教案”。
- 必须流式输出完整教案。
- 教案包含：教材分析、学情分析、教学目标、重难点、教学准备、教学过程、板书、作业、反思。
- 规范性判断尽量绑定 `evidence_ids`。
- 活动设计可吸收 `reference_ids`，显示为参考做法。

### 考点分析

- 只检索 `normative`。
- 缺教材、课标、考纲、单元目标或考试资料时，返回“依据不足”。
- 不允许模型凭空生成考点结论。

### 同行参考

- 只检索 `method_case`。
- 输出“参考路径 / 可借鉴做法 / 适用场景”。
- 不使用“权威依据”“证明”等措辞。

### 辅导说明

- 基于当前教案、normative evidence、method_case references。
- 必须先声明“依据与参考边界”。
- 没有规范依据时，不输出“符合课标/教材要求/单元语文要素”等权威判断。
- 重点解释：目标依据、重难点依据、活动设计思路、可改进处、年轻老师可学习的方法。

## 6. 后端 API

当前已落地的业务接口：

- `POST /api/teaching-evidence/search`
- `GET /api/evidence/{evidence_id}`
- `POST /api/generate/stream`
- `POST /api/generate/exam`
- `POST /api/generate/peer`
- `POST /api/generate/guide`
- `GET /api/history/{record_id}`
- `GET /api/export/{record_id}?format=md|docx`
- `GET /api/admin/evidence-coverage`

DEE 集成方式：

- 不需要单独部署 DEE 服务。
- 入库时把 DEE 的 `page_num`、`page_width`、`page_height`、`bbox`、`source_hash`、`page_image_url` 等字段保存在 LeKai 本地索引。
- `/api/teaching-evidence/search` 只查询本机知识库，按 `source_role` 和 `doc_type` 做分层过滤。
- `from_dee_evidence_object()` 只作为导入/迁移兼容入口，不作为运行时远程依赖。

`/api/teaching-evidence/search` 请求示例：

```json
{
  "grade": "三年级",
  "semester": "上",
  "lesson": "秋天的雨",
  "purpose": "lesson_plan",
  "source_roles": ["normative", "method_case"],
  "doc_types": ["textbook", "teaching_guidance"],
  "max_items": 20
}
```

响应：

```json
{
  "evidence": [],
  "missing": ["缺少教材、课标、考纲或单元目标等规范性依据"]
}
```

## 7. 前端交互

页面顺序：

1. 先展示完整教案正文，支持流式输出。
2. 教案下方展示“依据与参考”面板。
3. 规范材料显示为 `依据：教材 / 课标 / 考纲`。
4. 方法材料显示为 `参考：教学设计指导 / 老教师案例 / 本校案例`。
5. 点击 evidence/reference 后打开详情。
6. 如果 evidence 带 `page_image_url + bbox + page_width/page_height`，前端直接绘制 bbox 高亮。
7. 如果历史材料带旧的 `dee_url`，前端可显示原文链接；新部署不依赖外部 DEE URL。
8. 导出 `.md` / `.docx` 时，文末附“依据与参考附录”。

## 8. 已修改模块

- `backend/teaching_evidence.py`：内嵌教学证据模型、DEE EvidenceObject 导入兼容、分层检索、block 构建、citation validation。
- `backend/rag.py`：四个生成功能的 prompt 和证据分层逻辑。
- `backend/main.py`：新增 evidence API、流式生成保存元数据、分功能写回历史、导出附录、上传 doc_type/source_role。
- `backend/auth.py`：历史记录保存 evidence/block/missing/citation 元数据。
- `backend/search_engine.py`：检索结果返回 chunk id，供 evidence 引用。
- `scripts/ingest_knowledge.py`：入库时推断 doc_type/source_role，保留 DEE 页码、bbox、hash、页图、原文链接字段。
- `frontend/src/app/page.tsx`：依据/参考状态、历史回显、详情面板、bbox 高亮承载位。
- `frontend/src/app/admin/page.tsx`：上传材料强制标注 `doc_type/source_role`，新增“依据覆盖”页面。
- `frontend/src/app/api/[...path]/route.ts`：前端代理后端 API。
- `frontend/package.json`：本地 dev 使用 webpack，规避当前 Turbopack SWC helper 缓存问题。

## 9. 当前状态

已完成最小闭环：

- 能快速流式生成完整教案。
- 生成历史保存 `GeneratedBlock[]` 和 `TeachingEvidence[]`。
- 考点分析在缺少规范材料时返回“依据不足”。
- 同行参考只使用 `method_case`。
- 辅导说明明确区分“规范依据”和“方法参考”。
- 前端面板区分“依据”和“参考”。
- 导出包含“依据与参考附录”。
- 管理端上传材料必须选择文档类型和材料角色。
- 管理端可检查某课是否缺教材、课标/考纲/单元目标和方法案例。
- 管理端可统计真实生成历史中的“依据不足”记录、缺失材料类型和不足模块。

当前知识库已加入占位材料用于功能联调：

- 每个现有课题补齐 `textbook`、`curriculum_standard`、`exam_outline`、`unit_goal`、`exam_material` 五类规范依据占位。
- 每个现有课题补齐 `teaching_guidance`、`teacher_case` 两类方法参考占位。
- 占位材料带 `page_num`、`page_width`、`page_height`、`bbox`、`source_hash` 字段，用来验证依据面板、导出附录和 block citation 链路。
- 占位材料仅解决“数量和有无”，正式交付前必须替换为授权教材、课标、考纲、单元目标、题库和真实案例。

已补充扫描 PDF OCR 入库：

- 管理端上传支持 `.pdf`。
- 扫描 PDF 使用 `pypdfium2` 渲染页图，使用 Tesseract `chi_sim+eng` 做 OCR。
- OCR 结果按页生成 Markdown 证据文件，并保留 `page_num`、`page_width`、`page_height`、`bbox`、`page_image_url`、`source_hash`。
- 页图保存在 `data/source_pages/<source_hash>/page_XXXX.png`，前端依据详情可直接显示并高亮 bbox。
- PDF 上传大小由 `PDF_UPLOAD_MAX_MB` 控制，默认 1024MB。
- OCR 页数由 `PDF_OCR_MAX_PAGES` 控制，默认 80 页；大体量 PDF 建议后续升级为后台任务队列。

## 10. 下一阶段任务

### Phase 2 补强

- 让模型直接输出结构化 `GeneratedBlock[]`，减少当前启发式分段。
- 在关键段落旁显示 block 级“依据不足”标记。
- 给导出附录增加 block 到 evidence/reference 的映射。

### Phase 3：内嵌原文高亮

- 入库流程生成或保存页面图像 URL。
- 从导入的 EvidenceObject 字段转换为 `TeachingEvidence[]`。
- evidence 详情使用本地 `page_image_url` 和 bbox 坐标。
- 历史记录重新打开后仍能在 LeKai 内显示原文页和高亮框。

### Phase 4：知识库管理闭环

- 已完成：管理端上传时强制选择 `doc_type` 和 `source_role`。
- 已完成：规范材料上传后保留原文，只补 frontmatter，不使用教案格式化 prompt 改写原始依据。
- 已完成：依据覆盖度健康检查：
  - 本课是否有教材。
  - 是否有课标/考纲/单元目标。
  - 是否有方法案例。
- 已完成：依据不足统计，指导后续补资料。
- 已完成：占位知识库生成脚本 `scripts/create_placeholder_knowledge.py`，用于在正式材料到位前跑通全功能。
- 已完成：扫描 PDF OCR 入库最小闭环，真实扫描 PDF 已验证可上传、OCR、入库并返回页图/bbox。
- 增加教研组审核与沉淀：优秀教案进入 method_case，本校规范资料进入 normative。
