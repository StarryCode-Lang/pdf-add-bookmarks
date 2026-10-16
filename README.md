# PDF Add Bookmarks

为中英文文本、扫描和混合 PDF 添加分层书签的轻量 Skill。在 PDF 阅读器或笔记 App 的侧栏生成可点击的导航目录，点击后跳到对应页面。支持标准 Agent Skills；仅写入 outline，不修改正文、图片或页面排版。

## 安装到 Agent

需要 Node.js/npm 和 Git（推荐 Node.js 24）。使用 [Vercel Skills CLI](https://github.com/vercel-labs/skills)：

```bash
# 交互选择 Agent、全局/项目安装范围及复制/链接方式
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks

# Codex：全局安装，在所有项目中使用
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex --global --yes

# Codex：安装到当前项目，先进入项目目录
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex --yes

# 同时安装到多个 Agent
npx skills@1.7.2 add StarryCode-Lang/pdf-add-bookmarks --agent codex claude-code cursor opencode --global --yes
```

固定的 Skills CLI 1.7.2 将 Codex、Cursor、OpenCode 安装到共享的 `.agents/skills`（全局为 `~/.agents/skills`），Claude Code 使用 `.claude/skills`；由安装器按 Agent 规则处理路径。

`--agent` 也支持 `gemini-cli`、`github-copilot`、`qoder`、`qwen-code` 等；由安装器管理各 Agent 的目录。使用 `--copy` 可复制文件，`--all` 可选择全部支持的 Agent。全局安装不会替代已有项目级安装。

```bash
# 查看全局安装
npx skills@1.7.2 list --global --agent codex
# 更新全局 Skill
npx skills@1.7.2 update pdf-add-bookmarks --global
# 卸载 Codex 的全局安装
npx skills@1.7.2 remove pdf-add-bookmarks --agent codex --global --yes
```

也可先 `npm install -g skills@1.7.2`，再将以上 `npx skills@1.7.2` 替换为 `skills`。仓库根目录即可被安装器发现，无需 npm 包或额外插件配置。上面的仓库安装命令跟随当前仓库，**不是固定发行版**；固定安装器版本也不会固定 Skill 版本。稳定版安装使用 Release 的固定 ZIP：

```bash
npx skills@1.7.2 add https://github.com/StarryCode-Lang/pdf-add-bookmarks/releases/download/v0.4.3/pdf-add-bookmarks.zip --agent codex --global --yes
```

也可下载 ZIP，核对同一 Release 的 `SHA256SUMS.txt` 后解压到 Agent 的 Skill 目录。更新命令可能跟随上游版本；需要复现时保留发行 ZIP 与其校验值。

安装器部署 Skill 文件；Python 依赖与系统 OCR 按 [SKILL.md](SKILL.md) 准备。需要 Python **3.10–3.13**；Windows、Ubuntu、macOS 均纳入 CI。纯文字 PDF 不需要 Tesseract，中文扫描需 `chi_sim`，英文扫描需 `eng`。

## 使用

让 Agent“给这个 PDF 添加分层书签”，或在 Skill 目录运行：

```bash
python -m pip install -r requirements.txt
python scripts/add_bookmarks.py input.pdf --json
python scripts/add_bookmarks.py --version
```

默认输出 `input_with_bookmarks.pdf`，保留输入；默认拒绝覆盖已有 PDF 或建议目录，明确需要替换时加 `--overwrite`。输出的书签替换原书签，不添加 OCR 文字层；请求阅读器打开书签侧栏（是否自动展开由阅读器设置决定）。复杂版面先审查目录：

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

- `--overwrite`：允许替换已有输出；即使启用，验证失败仍保留旧文件。`--analyze -o review.txt` 可指定建议目录路径。
- 自动识别统一返回 `quality: "unverified"` 和 `review_required: true`；`warnings` 为空仅表示未检测到具体风险，不表示准确率已验证。用户提供目录返回 `quality: "provided_toc"`，其正确性由用户审核。
- 检测到数字签名标记时拒绝分析和写入，避免重新保存使签名失效；不验证签名真伪，也不提供绕过保护的参数。请使用未签名原件。
- 分析 JSON 的 `ok: true` 仅表示命令完成；必须检查 `candidates`。零候选明确返回 `recognition_failure: "no_headings"`，需要人工目录回退。
- `--json`：stdout 为一个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。使用 Unicode 转义兼容非 UTF-8 终端。
- OCR 缺失或失败默认停止。明确接受缺失扫描页时才指定 `--allow-partial`，结果含 `partial: true` 与 `warnings`。工作进程异常仍报错。
- 保存后重开临时 PDF，精确核对全部书签的标题、层级和目标页；默认验证内容流、文字、页面尺寸、链接、批注、附件与元数据；`--verify full` 额外逐页比较像素。验证成功后才发布输出。
- `--type textbook|exam|slides|article` 限定规则。默认优先采用经正文印证的印刷目录；`--generate-toc` 保留其核心节点并添加正文叶节点，同时扩大较小加粗标题候选，导出建议目录和书签 PDF。扩展模式会产生更多候选，需要审核；其他选项见 `--help`。

内容校验确认页面保持一致；标题准确性由原文审核和公开评测验证。

自动结果的 `outline_policy` 区分 `printed_toc_preferred`（默认）与 `expanded_body`（`--generate-toc`）。JSON 的 `review_required`、`warnings` 与 `diagnostics` 提示审核要求及具体问题；所有自动结果仍为 `quality=unverified`，不把 OCR 成功当作准确率保证。诊断包含编号层级冲突、缺少父章、标题碎片、重复结构标题、未确认页码及目录漏读，并给出 PDF 页码。`partial` 仅表示 OCR 环境缺失导致的部分处理。

按语义构建“单元/篇 → 章 → 节”，缺少中间层时直接连接实际父节点。原生标题按位置合并分散的编号、标题与不同字号；原生目录支持同一行左右页码、点线引导符与前置页码；确认印刷目录后抑制额外视觉栏目，扫描目录配对标题行和对齐的页码列，并单独处理彩色文字及页码。只有正文标题或多个正文页码支持一致偏移时才采用印刷目录；不能确认时提示审核，不猜目标页。复杂彩色扫描仍可能漏字、错字，必要时核对原文后用 `--toc` 导入。

## 开发与评测

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m pytest -q
# pytest 仅收集 tests/，临时工具和依赖库的测试不计入项目测试数
# CI 强制 REQUIRE_OCR=1，缺少 OCR 时不可跳过测试
# 全部实书、压力测试及受控性能测量：Linux，需要网络和 chi_sim+eng
python tests/network_smoke.py
# 只复测选定样本
python tests/network_smoke.py zh-text zh-scan zh-exam zh-low
```

性能对照使用 Linux `/proc/self/status` 的 `VmHWM` 与子进程 `ru_maxrss`；其他平台可选择单个样本运行识别评测。全量评测需完整 Git 历史与对全部固定源站的网络访问；普通 CI 不下载实书。

CI 覆盖三平台 × Python 3.10–3.13，另检查 Ruff 与 npx 项目/全局安装。原始 PDF 与输出保存在忽略的 `validation/`；完整结构化结果保存在 [tests/benchmark_results.json](tests/benchmark_results.json)，并作为独立 Release 附件发布，包含来源哈希、参考目录、实际书签、漏检、额外候选与运行环境；源 PDF SHA-256 固定，原有书签清除后再识别，原书目录或预先人工标注作为参考。书籍和输出 PDF 不提交、不放入发行包。

<!-- benchmark-summary-start -->
本版重新验证 22 个样本、2,830 页；严格识别结果与页面内容保真分别核验。每项参考范围、实际目录及失败项见 JSON。

| 样本 | 页数 | 严格匹配 / 参考项 | 输出书签 |
| --- | --- | --- | --- |
| Think Python | 244 | 240/240 | 246 |
| Calculus Made Easy（章目标页） | 315 | 23/23 | 29 |
| 人教版数学七上 | 162 | 19/19 | 69 |
| 北京版数学七上（扫描） | 158 | 30/32 | 34 |
| 冀教版数学八上（扫描） | 177 | 29/34 | 31 |
| 数学试卷 | 16 | 4/4 | 5 |
| Think Java | 372 | 230/230 | 240 |
| 教科版物理（仅章级） | 133 | 6/6 | 149 |
| 苏科版物理（仅章级） | 134 | 5/5 | 103 |
| 湘教版地理（扫描） | 121 | 20/24 | 24 |
| 济南版生物 | 140 | 32/32 | 32 |
| 沪教版化学 | 154 | 35/35 | 40 |
| 粤教粤人版地理 | 109 | 22/22 | 23 |
| 北京版化学九下 | 122 | 22/22 | 22 |
| 人教版地理八上 | 120 | 19/19 | 20 |
| Flatland 旧扫描书 | 116 | 21/24 | 29 |
| BERT 双栏论文 | 16 | 29/29 | 31 |
| ALBERT（现为回归） | 17 | 26/26 | 26 |
| RoBERTa（现为回归） | 13 | 25/25 | 27 |
| ELECTRA（未调优重放） | 18 | 17/18 | 17 |
| ELMo（未调优重放） | 15 | 22/24 | 25 |
| 低质量派生扫描 | 158 | 17/32 | 27 |

相对 v0.4.2，既有样本的严格匹配数均未下降。Flatland 从 1/24、69 项改善为 21/24、29 项（precision 72.4%，recall 87.5%）；BERT 从零候选恢复至 29/29、31 项（precision 93.5%，recall 100%）。化学保持 35/35，输出由 41 减至 40 项（precision 87.5%）；生物 32/32、32 项，粤教地理 22/22、23 项。部分样本仅标注章或编号节，不能据此推断完整输出 precision。

仍有明确边界：低质量扫描为 17/32；Flatland 仍有 OCR 字母错误和 Part I 扉页定位偏差。ELECTRA 漏掉 3.5 Efficiency Analysis；ELMo 漏掉含希腊字母的 A.2 和 A.8，并有参考范围外子标题。两份保留样本未据其失败调优，本次重放不算全新盲测。原生标题、扫描标题与完整印刷目录需要分别评估，不声称全自动通用识别。

`--generate-toc` 的化学实测由上一版 90 项减至 84 项，保留全部 35 个核心参考节点及父子路径；实际目录见 `workflow_validation`。低质量扫描的 32 项人工目录通过独立六文件 Skill 的 CLI 导入和全页校验，不代表自动识别达到 32/32。另一次仅依据 Skill 和原书页面的独立使用试验，逐项审核 Flatland 的 24 项目录、修正扉页跳转后成功写入，116 页全页校验及重开书签检查均通过；这同样是人工审核回退证据。

受控 Linux 新进程 ABBA 顺序，两版各运行两次，固定依赖、语言模型和 200 DPI。以下为均值；微基准不代表整书普遍提速：

| 测量范围 | v0.4.2 → v0.4.3 耗时 | 父进程峰值 MiB | 最大子进程峰值 MiB |
| --- | --- | --- | --- |
| BERT 16 页提取与识别 | 0.36 → 0.39 秒 | 46.84 → 46.84 | 0.00 → 0.00 |
| Flatland 三页强制 OCR | 3.52 → 3.60 秒 | 82.65 → 82.71 | 185.56 → 184.08 |
| Flatland 六页完整校验 | 4.05 → 3.65 秒 | 410.24 → 438.76 | 0.00 → 0.00 |

进程峰值不能相加当作同时总内存。逐书提取耗时可能复用固定指纹的缓存，不作提速证据；本轮每份输出均重新保存并逐页比较像素。全部原始测量、实现哈希、版本比较和失败候选见 `maintenance_comparison` 等字段。

本机六页完整校验的父进程峰值内存有所增加，存在时间与内存权衡，不宣称降低内存。
<!-- benchmark-summary-end -->

严格匹配要求归一化后的标题、PDF 页码与深度一致。完整印刷目录样本评分全部输出；目录之外也可能有合法正文子标题，不能一概视为无效。其他样本只评价明确标注的章、节或目标页范围，不代表全文准确率。每份实际生成的自动 PDF 和人工目录回退 PDF 都逐页验证内容一致；识别正确性与页面保真分别核验。

已参与调优的教材、Flatland、BERT、ALBERT 和 RoBERTa 均标记为回归样本；历史首次失败、实际目录与实现哈希保留在报告中。ELECTRA 和 ELMo 未用于本版规则调优，但本次是预先固定标注后的保留样本重放，不称作全新盲测。先前临时试验中未持久保存的结果不补造；完整披露见 `blind_protocol`。这些样本的失败用于说明适用边界，不以回归成绩代替独立泛化证据。

`tests/fixtures/signed_pdf.b64` 是 6,455 字节真实 RSA/CMS 签名 PDF 的 Base64，不是仅填充签名标记的文件。签署使用专门的自签名测试证书；独立验证确认签名完整、有效，CI 用 OpenSSL CMS 每次校验签名和内容摘要，并测试拒绝处理后原件逐字节不变。不宣称该证书受公共 CA 信任。创建样本的私钥、签署工具和输入 PDF 均不提交，不加入运行依赖。


## 发布

版本由脚本中的 `VERSION` 统一管理。修改版本并推送 `main` 后，全部 CI 通过才创建尚不存在的 Release；已发布版本不会自动覆盖。发布后 CI 直接下载公开 ZIP 与评测报告，校验 SHA-256 和全部源码内容，验证四个 Agent 的项目/全局安装，并用安装后的入口完成书签写入与全页校验。发行 ZIP 仅含运行 Skill：`SKILL.md`、三个脚本、`requirements.txt` 与 `LICENSE`。评测报告单独附加，ZIP 和报告均有 SHA-256 校验值。入口、标题/层级、OCR 按职责拆分，不引入额外运行依赖。

需要完全复现安装器时，可在固定仓库版本运行 `npm ci --prefix .github/skills --ignore-scripts`，再用 `node .github/skills/node_modules/skills/dist/cli.mjs add <固定发行ZIP的URL>` 安装；普通 npx 固定入口版本，传递依赖仍按上游声明解析。

Python 依赖固定到评测使用的版本；Actions 固定到提交 SHA，OCR 语言模型固定到提交，CI 安装器用 npm lock 固定版本、传递依赖与完整性哈希。这些固定项应在更新时一起复测；Windows CI 直接安装官方发布的固定 Tesseract 5.5.0 安装包并校验 SHA-256，避免最新 Chocolatey 包下载故障；其他平台由系统包管理器安装。评测环境版本单独记录。

<!-- release-notes -->
### v0.4.3

- 按列恢复正文阅读顺序，合并相邻编号与跨行标题；识别缺失粗体标志的嵌入字体和小型大写字母，恢复论文及附录层级。
- 扫描标题保留显式 § 结构，按 OCR 段落合并标题；抑制重复页眉，同页冲突节号仅在前后相邻节号共同印证时选择已有候选，不按词表猜字。
- 同页标题去重优先保留可靠印刷目录；扩展模式保留核心目录及父子路径。零候选分析明确返回 `recognition_failure: "no_headings"`。
- 保存后重开并精确核对书签；保持原有内容、签名拒绝、覆盖保护与 OCR 失败策略。直接编码及原始流完全一致时，省去重复解码；完整验证仍逐页比较像素。
- 真实文档、失败候选与性能证据独立发布；已用于调优的文档列为回归样本，未参与调优的保留样本明确说明重放状态。低质量扫描仍需审核及人工目录回退。
- 发行包仍为六个文件，无新增运行依赖。

MIT License。
