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
npx skills@1.7.2 add https://github.com/StarryCode-Lang/pdf-add-bookmarks/releases/download/v0.4.1/pdf-add-bookmarks.zip --agent codex --global --yes
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
- `--json`：stdout 为一个 JSON 对象，进度在 stderr；成功退出码 0，失败 1。使用 Unicode 转义兼容非 UTF-8 终端。
- OCR 缺失或失败默认停止。明确接受缺失扫描页时才指定 `--allow-partial`，结果含 `partial: true` 与 `warnings`。工作进程异常仍报错。
- 默认验证内容流、文字、页面尺寸、链接、批注、附件与元数据；`--verify full` 额外逐页比较像素。验证成功后才发布输出。
- `--type textbook|exam|slides|article` 限定规则；`--generate-toc` 扩展较小加粗标题候选，导出建议目录和书签 PDF。其他选项见 `--help`。

内容校验确认页面保持一致；标题准确性由原文审核和公开评测验证。

JSON 的 `review_required`、`warnings` 与 `diagnostics` 提示审核要求及具体问题；所有自动结果仍为 `quality=unverified`，不把 OCR 成功当作准确率保证。诊断包含编号层级冲突、缺少父章、标题碎片、重复结构标题、未确认页码及目录漏读，并给出 PDF 页码。`partial` 仅表示 OCR 环境缺失导致的部分处理。

按语义构建“单元/篇 → 章 → 节”，缺少中间层时直接连接实际父节点。原生标题按位置合并分散的编号、标题与不同字号；原生目录支持同一行左右页码、点线引导符与前置页码；确认印刷目录后抑制额外视觉栏目，扫描目录配对标题行和对齐的页码列，并单独处理彩色文字及页码。只有正文标题或多个正文页码支持一致偏移时才采用印刷目录；不能确认时提示审核，不猜目标页。复杂彩色扫描仍可能漏字、错字，必要时核对原文后用 `--toc` 导入。

## 开发与评测

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m pytest -q
# pytest 仅收集 tests/，临时工具和依赖库的测试不计入项目测试数
# CI 强制 REQUIRE_OCR=1，缺少 OCR 时不可跳过测试
# 全部实书与压力测试，需要网络和 chi_sim+eng
python tests/network_smoke.py
# 只复测选定样本
python tests/network_smoke.py zh-text zh-scan zh-exam zh-low
```

CI 覆盖三平台 × Python 3.10–3.13，另检查 Ruff 与 npx 项目/全局安装。原始 PDF 与输出保存在忽略的 `validation/`；完整结构化结果保存在 [tests/benchmark_results.json](tests/benchmark_results.json)，并作为独立 Release 附件发布，包含来源哈希、参考目录、实际书签、漏检、额外候选与运行环境；源 PDF SHA-256 固定，原有书签清除后再识别，原书目录或预先人工标注作为参考。书籍和输出 PDF 不提交、不放入发行包。

<!-- benchmark-summary-start -->
本版共 16 个样本、2,635 页；以下为本地实测，环境、来源、范围和逐项结果以 JSON 为准。

| 样本 | 页数 | 严格匹配 / 参考项 | 输出书签 |
| --- | --- | --- | --- |
| Think Python（文字，回归） | 244 | 240/240 | 246 |
| Calculus Made Easy（扫描，回归） | 315 | 23/23 章目标页 | 29 |
| 人教版数学七上（回归） | 162 | 19/19 | 70 |
| 北京版数学七上（彩色扫描，回归） | 158 | 30/32 | 34 |
| 冀教版数学八上（扫描，回归） | 177 | 29/34 | 32 |
| 数学试卷（回归） | 16 | 4/4 | 5 |
| Think Java（文字，回归） | 372 | 230/230 | 240 |
| 教科版物理八上（混合，回归） | 133 | 6/6 | 147 |
| 苏科版物理八上（混合，回归） | 134 | 5/5 | 105 |
| 湘教版地理七上（扫描，回归） | 121 | 20/24 | 24 |
| 济南版生物七上（混合，回归） | 140 | 32/32 | 32 |
| 沪教版化学九上（混合，现为回归） | 154 | 35/35 | 41 |
| 粤教粤人版地理七上（混合，现为回归） | 109 | 22/22 | 23 |
| 北京版化学九下（新盲测） | 122 | 22/22 | 22 |
| 人教版地理八上（新盲测） | 120 | 19/19 | 20 |
| 北京版低质量派生扫描（压力测试） | 158 | 16/32 | 27 |

沪教版化学的输出从 89 降至 41，35 项参考目录全部严格匹配（原为 34/35）；粤教粤人版地理由 102 降至 23，保留 22/22。额外明确结构标题仍计入完整目录 precision 的分母，不通过删掉评测候选提高分数。两份已用于调优的书籍不再称为盲测。

新盲测的完整逐项分类、漏检、额外候选与诊断见 JSON；算法冻结后不按新盲测成绩修改。扫描地理与低质量样本仍存在 OCR 字词错误；自动目录仍需人工审核。
新盲测北京版化学 22/22、22 项输出（precision 100%），人教版地理 19/19、20 项输出（precision 95%）；两者 recall 均为 100%。额外地理书签为后记，仍计入分母。这些指标仅对应两份预先标注的完整印刷目录。

受控 Linux 复测使用四个 OCR 进程、200 DPI，每版两次并交替顺序，未复用识别缓存：

| 样本 | 提取耗时，旧版 → 新版 | 父进程峰值 MiB | 最大子进程峰值 MiB |
| --- | --- | --- | --- |
| 沪教版化学 | 5.99 → 7.04 秒 | 156.6 → 157.2 | 181.1 → 181.1 |
| 粤教粤人版地理 | 31.48 → 30.66 秒 | 203.0 → 204.1 | 202.8 → 216.2 |

提取包含原生分析、OCR 与布局；内存是 Linux 内核记录的各进程峰值，不能相加当作同时总内存。单页 OCR 探针输出哈希一致。样本与重复次数有限，不宣称普遍提速；本轮以更准确的目录换取少量处理开销，没有降低 OCR 分辨率或缩减 CI 覆盖。完整原始测量、历史 CI 耗时与重现方法见 JSON 的 `maintenance_comparison`。
<!-- benchmark-summary-end -->

严格匹配要求归一化后的标题、PDF 页码与深度一致。完整印刷目录样本评分全部输出；目录之外也可能有合法正文子标题，不能一概视为无效。其他样本只评价明确标注的章、节或目标页范围，不代表全文准确率。每次自动输出和中文人工目录回退都逐页验证内容一致；识别正确性与页面保真分别核验。

已参与调优的教材均标记为回归样本；v0.3.3 与 v0.4.0 的首次失败数据、实际目录和实现哈希保存在报告 `prior_independent_evaluations`。苏科版早期首次 0/5 保存在 `independent_first_pass`。新盲测先标注完整目录再运行冻结算法，测试后不因其成绩调整本版识别规则。历史分数和各样本范围详见 JSON，不以回归成绩代替独立泛化证据。

`tests/fixtures/signed_pdf.b64` 是 6,455 字节真实 RSA/CMS 签名 PDF 的 Base64，不是仅填充签名标记的文件。签署使用专门的自签名测试证书；独立验证确认签名完整、有效，CI 用 OpenSSL CMS 每次校验签名和内容摘要，并测试拒绝处理后原件逐字节不变。不宣称该证书受公共 CA 信任。创建样本的私钥、签署工具和输入 PDF 均不提交，不加入运行依赖。


## 发布

版本由脚本中的 `VERSION` 统一管理。修改版本并推送 `main` 后，全部 CI 通过才创建尚不存在的 Release；已发布版本不会自动覆盖。发布后 CI 直接下载公开 ZIP 与评测报告，校验 SHA-256 和全部源码内容，验证四个 Agent 的项目/全局安装，并用安装后的入口完成书签写入与全页校验。发行 ZIP 仅含运行 Skill：`SKILL.md`、三个脚本、`requirements.txt` 与 `LICENSE`。评测报告单独附加，ZIP 和报告均有 SHA-256 校验值。入口、标题/层级、OCR 按职责拆分，不引入额外运行依赖。

需要完全复现安装器时，可在固定仓库版本运行 `npm ci --prefix .github/skills --ignore-scripts`，再用 `node .github/skills/node_modules/skills/dist/cli.mjs add <固定发行ZIP的URL>` 安装；普通 npx 固定入口版本，传递依赖仍按上游声明解析。

Python 依赖固定到评测使用的版本；Actions 固定到提交 SHA，OCR 语言模型固定到提交，CI 安装器用 npm lock 固定版本、传递依赖与完整性哈希。这些固定项应在更新时一起复测；Windows CI 直接安装官方发布的固定 Tesseract 5.5.0 安装包并校验 SHA-256，避免最新 Chocolatey 包下载故障；其他平台由系统包管理器安装。评测环境版本单独记录。

<!-- release-notes -->
### v0.4.1

- 解析带点线/横线或前置页码的原生印刷目录，包括续页、实验、归纳与作业；用正文证据确认页码偏移。
- 有可靠印刷目录时抑制通用视觉栏目，保留目录范围外的明确结构标题；修正原生“附 录”层级，删除重复规范化规则。
- 新增回归测试，重新处理全部实书并逐页验证页面内容；两份新教材在冻结识别代码后盲测，保留历史失败证据。
- 运行包仍为六个文件，无新增依赖；自动结果仍需人工审核。

MIT License。
