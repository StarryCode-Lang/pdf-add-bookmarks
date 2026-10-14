# PDF Add Bookmarks

为中英文文本、扫描和混合 PDF 添加分层书签的轻量 Skill。核心仅 `SKILL.md`、`scripts/add_bookmarks.py`、`requirements.txt`，支持标准 Agent Skills。

## 安装到 Agent

需要 Node.js/npm 和 Git（推荐 Node.js 24）。使用 [Vercel Skills CLI](https://github.com/vercel-labs/skills)：

```bash
# 交互选择 Agent、全局/项目安装范围及复制/链接方式
npx skills add StarryCode-Lang/pdf-add-bookmarks

# Codex：全局安装，在所有项目中使用
npx skills add StarryCode-Lang/pdf-add-bookmarks --agent codex --global --yes

# Codex：安装到当前项目，先进入项目目录
npx skills add StarryCode-Lang/pdf-add-bookmarks --agent codex --yes

# 同时安装到多个 Agent
npx skills add StarryCode-Lang/pdf-add-bookmarks --agent codex claude-code cursor opencode --global --yes
```

`--agent` 也支持 `gemini-cli`、`github-copilot`、`qoder`、`qwen-code` 等；由安装器管理各 Agent 的目录。使用 `--copy` 可复制文件，`--all` 可选择全部支持的 Agent。全局安装不会替代已有项目级安装。

```bash
# 查看全局安装
npx skills list --global --agent codex
# 更新全局 Skill
npx skills update pdf-add-bookmarks --global
# 卸载 Codex 的全局安装
npx skills remove pdf-add-bookmarks --agent codex --global --yes
```

也可先 `npm install -g skills`，再将以上 `npx skills` 替换为 `skills`。仓库根目录即可被安装器发现，无需 npm 包或额外插件配置。固定版本可下载 [Release](https://github.com/StarryCode-Lang/pdf-add-bookmarks/releases) 的精简 ZIP，解压到 Agent 的 Skill 目录。

安装器部署 Skill 文件；Python 依赖与系统 OCR 按 [SKILL.md](SKILL.md) 准备。需要 Python **3.10–3.13**；Windows、Ubuntu、macOS 均纳入 CI。纯文字 PDF 不需要 Tesseract，中文扫描需 `chi_sim`，英文扫描需 `eng`。

## 使用

让 Agent“给这个 PDF 添加分层书签”，或在 Skill 目录运行：

```bash
python -m pip install -r requirements.txt
python scripts/add_bookmarks.py input.pdf --json
python scripts/add_bookmarks.py --version
```

默认输出 `input_with_bookmarks.pdf`，保留输入，替换输出的原有书签，不添加 OCR 文字层。复杂版面先审查目录：

```bash
python scripts/add_bookmarks.py input.pdf --analyze --json
python scripts/add_bookmarks.py input.pdf --toc input_suggested_toc.txt -o output.pdf
```

目录使用 **从 1 开始的 PDF 页码**；标题与页码之间用 TAB、两个以上空格或连续点号，缩进表示层级。旧版单空格格式需转换；印刷页码可用 `--offset N` 调整。

```text
第1章 概述  5
  1.1 背景  6
第2章 方法  12
```

- `--json`：stdout 为一个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。使用 Unicode 转义兼容非 UTF-8 终端。
- OCR 缺失或失败默认停止。明确接受缺失扫描页时才指定 `--allow-partial`，结果含 `partial: true` 与 `warnings`。工作进程异常仍报错。
- 默认验证内容流、文字、页面尺寸、链接、批注、附件与元数据；`--verify full` 额外逐页比较像素。验证成功后才替换输出。
- `--type textbook|exam|slides|article` 限定规则；`--generate-toc` 扩展较小加粗标题候选，导出建议目录和书签 PDF。其他选项见 `--help`。

书签定位到页面。彩色图文背景、图框栏目、低质量扫描和公式可能漏判或误判，应审查建议目录；无法可靠识别时按原文提供 `--toc`。

## 开发与评测

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m pytest -q
# CI 强制 REQUIRE_OCR=1，缺少 OCR 时不可跳过测试
# 全部实书与压力测试，需要网络和 chi_sim+eng
python tests/network_smoke.py
# 只复测选定样本
python tests/network_smoke.py zh-text zh-scan zh-exam zh-low
```

CI 覆盖三平台 × Python 3.10–3.13，另检查 Ruff 与 npx 项目/全局安装。评测下载和完整证据保存在忽略的 `validation/`；源 PDF SHA-256 固定，原有书签清除后再识别，原书目录或预先人工标注作为参考。书籍和输出 PDF 不提交、不放入发行包。

| 样本 | 参考范围 |
| --- | --- |
| Think Python，244 页文字版 | 原书 240 项标题、页码、层级 |
| Calculus Made Easy，315 页原始扫描版 | 印刷目录 23 章目标页 |
| 人教版数学七年级上册，162 页文字版 | 4 章与 15 个编号节 |
| 北京版数学七年级上册，158 页彩色扫描版 | 3 章与 29 个编号节 |
| 2025 年新高考 I 卷数学回忆版含解析，16 页扫描版 | 试题部分 4 个大题标题 |
| 北京版教材低质量派生版，158 页 | 100 DPI 灰度、JPEG 质量 30；同一教材的压力测试 |

指标只覆盖表中的参考范围，其他视觉候选单独记录，不能将范围内 precision/recall 当作全文识别准确率。中文扫描保留漏检、误检及 OCR 拼写错误，人工审查后的目录导入也单独验证。

本地实测（PyMuPDF 1.26.6，Tesseract 5.3.4，200 DPI、4 个 OCR 进程）：

| 样本 | 参考严格匹配 | 范围内 precision / recall |
| --- | --- | --- |
| 英文文字书 | 240/240 | 参考召回 100%，另有 6 项未标注候选 |
| 英文扫描书 | 23/23 章目标页 | 仅页码，未评估全文标题 |
| 中文文字教材 | 19/19 | 100.0% / 100.0% |
| 中文彩色扫描教材 | 4/32 | 6.6% / 12.5% |
| 中文数学试卷 | 3/4 | 75.0% / 75.0% |
| 低质量派生版 | 3/32 | 6.1% / 9.4% |

严格匹配同时要求标题（忽略编号与标点）、PDF 页码和层级正确。文字教材的评测仅覆盖章和一级编号节；扫描结果不适合未经审查直接交付。所有自动输出均通过全部页的内容校验；4 个中文样本的人工参考目录导入及全页校验全部通过。试卷为网络回忆版，原文件的解析部分缺失印刷页 6–7，不作为完整真题来源。


## 发布

版本由脚本中的 `VERSION` 统一管理。修改版本并推送 `main` 后，全部 CI 通过才创建尚不存在的 Release；已发布版本不会自动覆盖。发行 ZIP 仅含 4 个文件（运行核心加 LICENSE），附 SHA-256 校验值。

<!-- release-notes -->
### v0.2.0

- 增加标准 npx Skills 安装说明与项目/全局安装验证，支持指定多个 Agent。
- 增加 Ruff 检查、统一格式及三平台 Python 3.10–3.13 测试。
- 扩大中文文字教材、彩色扫描教材、数学试卷与低质量派生样本评测，记录参考范围、precision/recall、漏检和额外候选。
- 改善全角编号、无空格中文标题、目录页过滤、大题说明文本及编号父级定位。
- 修正压缩 PDF 对象容器重新序列化引起的内容校验误报；增加版本查询。
- 保留已修复的 OCR 失败、JSON、原子输出行为。复杂扫描仍需审查建议目录或人工导入。

MIT License。
